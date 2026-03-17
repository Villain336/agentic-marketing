"""
Supervisor Backend — Agent Engine
The agentic reasoning loop: Plan → Act → Observe → Decide.
This is what makes agents REAL — not prompt templates.
"""
from __future__ import annotations
import json
import time
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from config import settings
from costtracker import cost_tracker
from models import (
    AgentRun, AgentStep, AgentStatus, AgentStreamEvent,
    CampaignMemory, StepType, Tier, ToolCall,
)
from providers import router, AllProvidersFailedError
from tools import registry

logger = logging.getLogger("supervisor.engine")

# Lazy import to avoid circular dependency
_adaptation_engine = None

def _get_adaptation_engine():
    global _adaptation_engine
    if _adaptation_engine is None:
        from adaptation import adaptation_engine
        _adaptation_engine = adaptation_engine
    return _adaptation_engine


class AgentConfig:
    """Configuration for a single agent."""
    def __init__(self, id, label, role, icon, system_prompt_builder, goal_prompt_builder,
                 memory_extractor, tool_categories, tier=Tier.STANDARD, max_iterations=15,
                 model=None):
        self.id = id
        self.label = label
        self.role = role
        self.icon = icon
        self.system_prompt_builder = system_prompt_builder
        self.goal_prompt_builder = goal_prompt_builder
        self.memory_extractor = memory_extractor
        self.tool_categories = tool_categories
        self.tier = tier
        self.max_iterations = max_iterations
        self.model = model  # OpenRouter model override e.g. "anthropic/claude-sonnet-4-20250514"

    def get_tools(self):
        return registry.get_definitions(categories=self.tool_categories)


class AgentEngine:
    """
    Runs a single agent through the ReAct loop:
    1. Send goal + tools to LLM
    2. If LLM returns tool_calls → execute tools → feed results back → loop
    3. If LLM returns text only → agent is done
    4. Extract memory from output → return
    Streams every step as SSE events.
    """

    async def run(self, agent: AgentConfig, memory: CampaignMemory,
                  campaign_id: str = "", tier: Tier = None,
                  campaign: "Campaign | None" = None,
                  trigger_reason: str = "") -> AsyncGenerator[AgentStreamEvent, None]:
        tier = tier or agent.tier
        system = agent.system_prompt_builder(memory)
        goal = agent.goal_prompt_builder(memory)

        # ── Adaptive Intelligence Injection ──
        adaptive_block = ""
        if campaign:
            try:
                adapt = _get_adaptation_engine()
                adaptive_ctx = adapt.build_context(
                    agent_id=agent.id, campaign=campaign,
                    trigger_reason=trigger_reason,
                )
                adaptive_block = adapt.render_prompt_block(adaptive_ctx)
                if adaptive_block:
                    system = system + "\n\n" + adaptive_block
            except Exception as e:
                logger.warning(f"Adaptation injection skipped for {agent.id}: {e}")
        tools = agent.get_tools()
        messages = [{"role": "user", "content": goal}]

        yield AgentStreamEvent(
            event=StepType.STATUS, agent_id=agent.id,
            content=f"{agent.label} starting — {len(tools)} tools available",
            status=AgentStatus.PLANNING,
        )

        full_text_output = ""
        iteration = 0
        max_iter = min(agent.max_iterations, settings.max_agent_iterations)
        start_time = time.time()

        while iteration < max_iter:
            iteration += 1
            if time.time() - start_time > settings.max_agent_runtime:
                yield AgentStreamEvent(event=StepType.ERROR, agent_id=agent.id,
                    content=f"Agent timed out after {int(time.time()-start_time)}s", status=AgentStatus.ERROR)
                return

            # ── Call LLM ──
            try:
                text_buffer = ""
                tool_calls: list[ToolCall] = []
                provider_used = ""
                model_used = ""

                async for chunk in router.complete_stream(
                    messages=messages, system=system,
                    tools=tools if tools else None,
                    tier=tier, max_tokens=settings.default_max_tokens,
                    model_override=agent.model,
                ):
                    if chunk["type"] == "text":
                        text_buffer += chunk["text"]
                        provider_used = chunk.get("provider", "")
                        model_used = chunk.get("model", "")
                        yield AgentStreamEvent(
                            event=StepType.THINK, agent_id=agent.id, step=iteration,
                            content=text_buffer, provider=provider_used, model=model_used,
                            status=AgentStatus.EXECUTING,
                        )
                    elif chunk["type"] == "tool_call":
                        tool_calls.append(chunk["tool_call"])
                        provider_used = chunk.get("provider", "")
                        model_used = chunk.get("model", "")
                    elif chunk["type"] == "done":
                        provider_used = chunk.get("provider", provider_used)
                        model_used = chunk.get("model", model_used)

            except AllProvidersFailedError as e:
                yield AgentStreamEvent(event=StepType.ERROR, agent_id=agent.id, step=iteration,
                    content=f"All LLM providers failed: {e}", status=AgentStatus.ERROR)
                return

            # ── Record LLM cost ──
            if provider_used and model_used and campaign_id:
                try:
                    input_len = sum(len(str(m.get("content", ""))) for m in messages)
                    cost_tracker.record(
                        campaign_id=campaign_id, agent_id=agent.id,
                        provider=provider_used, model=model_used,
                        input_tokens=input_len // 4,
                        output_tokens=len(text_buffer) // 4,
                    )
                except Exception:
                    pass  # Cost tracking is best-effort

            # ── Handle tool calls ──
            if tool_calls:
                # Build assistant message with text + tool_use blocks
                assistant_content = []
                if text_buffer:
                    assistant_content.append({"type": "text", "text": text_buffer})
                for tc in tool_calls:
                    assistant_content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool
                for tc in tool_calls:
                    yield AgentStreamEvent(
                        event=StepType.TOOL_CALL, agent_id=agent.id, step=iteration,
                        content=f"Calling {tc.name}", tool_name=tc.name, tool_input=tc.input,
                        provider=provider_used, model=model_used, status=AgentStatus.TOOL_CALLING,
                    )

                    result = await registry.execute(tc.name, tc.input, tc.id)

                    yield AgentStreamEvent(
                        event=StepType.TOOL_RESULT, agent_id=agent.id, step=iteration,
                        content=f"{tc.name} → {'OK' if result.success else 'ERROR'}",
                        tool_name=tc.name, tool_output=result.output[:2000] if result.output else result.error,
                        status=AgentStatus.OBSERVING,
                    )

                    # Feed tool result back into conversation (Anthropic format)
                    messages.append({
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                     "content": result.output if result.success else f"Error: {result.error}"}],
                    })

                continue  # Loop back — agent needs to process tool results

            # ── No tool calls = agent done ──
            if text_buffer:
                full_text_output += text_buffer
            break

        # ── Extract memory ──
        memory_update = {}
        if full_text_output:
            try:
                memory_update = agent.memory_extractor(full_text_output)
            except Exception as e:
                logger.error(f"Memory extraction failed for {agent.id}: {e}")

        total_ms = int((time.time() - start_time) * 1000)

        yield AgentStreamEvent(
            event=StepType.OUTPUT, agent_id=agent.id, step=iteration,
            content=full_text_output, provider=provider_used,
            status=AgentStatus.DONE, memory_update=memory_update,
        )

        # ── Record run snapshot for trend computation ──
        if campaign and campaign_id:
            try:
                from scoring import scorer
                adapt = _get_adaptation_engine()
                scores = scorer.score_all(campaign)
                agent_score = scores.get(agent.id, {}).get("score", 0)
                agent_metrics = scores.get(agent.id, {}).get("metrics", {})
                adapt.record_run_snapshot(
                    agent_id=agent.id, campaign_id=campaign_id,
                    score=agent_score, metrics=agent_metrics,
                )
            except Exception as e:
                logger.debug(f"Snapshot recording skipped for {agent.id}: {e}")

        logger.info(f"Agent {agent.id} done: {iteration} iterations, {total_ms}ms")


engine = AgentEngine()
