"""
E2E test for the full agent → tool → memory cycle.

Verifies the complete flow:
1. Agent engine receives a goal and tools
2. LLM streams back a tool call
3. Tool executes and returns result
4. LLM uses result to produce final output
5. Memory extractor captures structured data from output
6. OUTPUT event contains memory_update

Mocks the LLM provider (no real API calls) but exercises the real
engine loop, tool registry dispatch, and memory extraction path.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from models import (
    CampaignMemory, StepType, Tier, ToolCall, ToolResult,
    AgentStreamEvent, AgentStatus,
)
from engine import AgentEngine, AgentConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_agent(tool_categories=None):
    """Create a minimal agent config for testing."""
    return AgentConfig(
        id="test_prospector",
        label="Test Prospector",
        role="Find leads",
        icon="T",
        system_prompt_builder=lambda m: "You are a test prospector agent.",
        goal_prompt_builder=lambda m: "Find 2 companies that match the ICP.",
        memory_extractor=lambda output: {"prospects": output[:200], "prospect_count": 2},
        tool_categories=tool_categories or ["web"],
        tier=Tier.STANDARD,
        max_iterations=5,
    )


async def _fake_stream_with_tool(*args, **kwargs):
    """Simulate LLM streaming: text → tool_call → done."""
    yield {"type": "text", "text": "I'll search for companies matching the ICP.", "provider": "test", "model": "test-1"}
    yield {
        "type": "tool_call",
        "tool_call": ToolCall(id="call-001", name="web_search", input={"query": "B2B SaaS companies"}),
        "provider": "test",
        "model": "test-1",
    }
    yield {"type": "done", "provider": "test", "model": "test-1", "usage": {"input_tokens": 150, "output_tokens": 80}}


async def _fake_stream_final(*args, **kwargs):
    """Simulate LLM streaming: final text output (no more tools)."""
    yield {
        "type": "text",
        "text": "Found 2 companies:\n1. Acme Inc (CTO: Alice)\n2. Globex Corp (VP Sales: Bob)\nBoth match the ICP criteria.",
        "provider": "test",
        "model": "test-1",
    }
    yield {"type": "done", "provider": "test", "model": "test-1", "usage": {"input_tokens": 300, "output_tokens": 60}}


# ═══════════════════════════════════════════════════════════════════════════════
# E2E TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentToolMemoryCycle:
    """Full cycle: agent run → tool execution → memory extraction."""

    @pytest.mark.asyncio
    async def test_full_cycle(self, business_profile):
        """Agent calls a tool, gets result, produces output with memory update."""
        memory = CampaignMemory(business=business_profile)
        agent = _make_agent()
        call_count = 0

        async def _stream_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                async for chunk in _fake_stream_with_tool():
                    yield chunk
            else:
                async for chunk in _fake_stream_final():
                    yield chunk

        with patch("engine.router") as mock_router, \
             patch("engine.registry") as mock_registry, \
             patch("engine.cost_tracker") as mock_cost, \
             patch("engine._get_event_bus") as mock_bus_fn, \
             patch("engine.settings") as mock_settings:

            # Configure settings
            mock_settings.max_agent_iterations = 15
            mock_settings.max_agent_runtime = 300
            mock_settings.default_max_tokens = 4096

            # Mock event bus
            bus = MagicMock()
            bus.agent_started = AsyncMock()
            bus.agent_completed = AsyncMock()
            bus.tool_executed = AsyncMock()
            mock_bus_fn.return_value = bus

            # Mock LLM streaming
            mock_router.complete_stream = MagicMock(side_effect=_stream_side_effect)

            # Mock tool registry
            mock_registry.get_definitions.return_value = [
                MagicMock(name="web_search", description="Search the web", parameters=[], category="web"),
            ]
            mock_registry.execute = AsyncMock(return_value=ToolResult(
                tool_call_id="call-001",
                name="web_search",
                output=json.dumps({"results": [
                    {"title": "Acme Inc", "url": "https://acme.com", "snippet": "B2B SaaS platform"},
                    {"title": "Globex Corp", "url": "https://globex.com", "snippet": "Enterprise sales tool"},
                ]}),
                success=True,
            ))

            # Mock cost tracker
            mock_cost.record = MagicMock()

            # Run agent and collect events
            engine = AgentEngine()
            events: list[AgentStreamEvent] = []
            async for event in engine.run(agent, memory, campaign_id="test-e2e-001"):
                events.append(event)

        # ── Assertions ──

        event_types = [e.event for e in events]

        # 1. Agent produced a STATUS (starting) event
        assert StepType.STATUS in event_types, f"No STATUS event. Got: {event_types}"

        # 2. Agent called a tool
        assert StepType.TOOL_CALL in event_types, f"No TOOL_CALL event. Got: {event_types}"
        tool_call_events = [e for e in events if e.event == StepType.TOOL_CALL]
        assert tool_call_events[0].tool_name == "web_search"

        # 3. Tool result came back
        assert StepType.TOOL_RESULT in event_types, f"No TOOL_RESULT event. Got: {event_types}"
        tool_result_events = [e for e in events if e.event == StepType.TOOL_RESULT]
        assert "OK" in tool_result_events[0].content

        # 4. Agent produced final output
        assert StepType.OUTPUT in event_types, f"No OUTPUT event. Got: {event_types}"
        output_event = [e for e in events if e.event == StepType.OUTPUT][-1]
        assert len(output_event.content) > 0, "Output content is empty"

        # 5. Memory was extracted and attached
        assert output_event.memory_update is not None, "No memory_update in output event"
        assert "prospects" in output_event.memory_update, "Memory missing 'prospects' key"
        assert output_event.memory_update["prospect_count"] == 2

        # 6. Tool was actually executed
        mock_registry.execute.assert_called_once()
        call_args = mock_registry.execute.call_args
        assert call_args[0][0] == "web_search"  # tool name

        # 7. Cost was tracked
        assert mock_cost.record.call_count >= 1

        # 8. Event bus was notified
        bus.agent_started.assert_called_once()
        bus.agent_completed.assert_called_once()
        bus.tool_executed.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_failure_does_not_crash(self, business_profile):
        """Agent continues gracefully when a tool fails."""
        memory = CampaignMemory(business=business_profile)
        agent = _make_agent()
        call_count = 0

        async def _stream_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                async for chunk in _fake_stream_with_tool():
                    yield chunk
            else:
                async for chunk in _fake_stream_final():
                    yield chunk

        with patch("engine.router") as mock_router, \
             patch("engine.registry") as mock_registry, \
             patch("engine.cost_tracker"), \
             patch("engine._get_event_bus") as mock_bus_fn, \
             patch("engine.settings") as mock_settings:

            mock_settings.max_agent_iterations = 15
            mock_settings.max_agent_runtime = 300
            mock_settings.default_max_tokens = 4096

            bus = MagicMock()
            bus.agent_started = AsyncMock()
            bus.agent_completed = AsyncMock()
            bus.agent_failed = AsyncMock()
            bus.tool_executed = AsyncMock()
            mock_bus_fn.return_value = bus

            mock_router.complete_stream = MagicMock(side_effect=_stream_side_effect)
            mock_registry.get_definitions.return_value = [
                MagicMock(name="web_search", description="Search", parameters=[], category="web"),
            ]
            # Tool fails
            mock_registry.execute = AsyncMock(return_value=ToolResult(
                tool_call_id="call-001", name="web_search",
                output="", error="API key not configured", success=False,
            ))

            engine = AgentEngine()
            events = []
            async for event in engine.run(agent, memory, campaign_id="test-e2e-002"):
                events.append(event)

        event_types = [e.event for e in events]

        # Agent should still produce output (even if tool failed)
        assert StepType.TOOL_RESULT in event_types
        tool_result = [e for e in events if e.event == StepType.TOOL_RESULT][0]
        assert "ERROR" in tool_result.content

        # Agent should still finish with an output
        assert StepType.OUTPUT in event_types

    @pytest.mark.asyncio
    async def test_no_tool_calls_still_produces_output(self, business_profile):
        """Agent that doesn't call tools still produces output with memory."""
        memory = CampaignMemory(business=business_profile)
        agent = _make_agent()

        with patch("engine.router") as mock_router, \
             patch("engine.registry") as mock_registry, \
             patch("engine.cost_tracker"), \
             patch("engine._get_event_bus") as mock_bus_fn, \
             patch("engine.settings") as mock_settings:

            mock_settings.max_agent_iterations = 15
            mock_settings.max_agent_runtime = 300
            mock_settings.default_max_tokens = 4096

            bus = MagicMock()
            bus.agent_started = AsyncMock()
            bus.agent_completed = AsyncMock()
            mock_bus_fn.return_value = bus

            mock_router.complete_stream = MagicMock(side_effect=_fake_stream_final)
            mock_registry.get_definitions.return_value = []

            engine = AgentEngine()
            events = []
            async for event in engine.run(agent, memory, campaign_id="test-e2e-003"):
                events.append(event)

        event_types = [e.event for e in events]

        # No tool calls
        assert StepType.TOOL_CALL not in event_types

        # Still got output with memory
        assert StepType.OUTPUT in event_types
        output_event = [e for e in events if e.event == StepType.OUTPUT][-1]
        assert output_event.memory_update is not None
        assert "prospects" in output_event.memory_update
