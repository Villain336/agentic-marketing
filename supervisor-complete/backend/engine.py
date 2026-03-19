"""
Omni OS Backend — Agent Engine (Production Grade)
The agentic reasoning loop: Plan → Act → Observe → Validate → Decide.
Includes: quality gate, tool retry with fallback, graceful timeout,
structured memory extraction, persistence at every step.
"""
from __future__ import annotations

import asyncio
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

logger = logging.getLogger("omnios.engine")

# ── Lazy imports to avoid circular deps ─────────────────────────────────────

_adaptation_engine = None
_replanner = None
_event_bus = None
_autonomy_store = None
_wallet = None


def _get_event_bus():
    global _event_bus
    if _event_bus is None:
        from eventbus import event_bus
        _event_bus = event_bus
    return _event_bus


def _get_autonomy_store():
    global _autonomy_store
    if _autonomy_store is None:
        from autonomy import autonomy_store
        _autonomy_store = autonomy_store
    return _autonomy_store


def _get_wallet():
    global _wallet
    if _wallet is None:
        from wallet import wallet
        _wallet = wallet
    return _wallet


# Estimated cost per tool execution (USD) for spend-tracking tools
TOOL_COST_ESTIMATES: dict[str, float] = {
    "send_email": 0.01, "schedule_email_sequence": 0.05, "send_sms": 0.05,
    "make_phone_call": 0.50, "post_twitter": 0.00, "post_linkedin": 0.00,
    "post_instagram": 0.00, "schedule_social_post": 0.00,
    "create_meta_ad_campaign": 5.00, "create_google_ads_campaign": 5.00,
    "create_linkedin_ad_campaign": 5.00, "deploy_to_vercel": 0.00,
    "deploy_to_cloudflare": 0.00, "register_domain": 15.00,
    "create_subscription": 0.00, "create_invoice": 0.00,
    "send_payment_reminder": 0.01, "publish_to_cms": 0.00,
    "create_referral_program": 0.00, "generate_image": 0.04,
    "generate_logo": 0.04,
}


def _get_adaptation_engine():
    global _adaptation_engine
    if _adaptation_engine is None:
        from adaptation import adaptation_engine
        _adaptation_engine = adaptation_engine
    return _adaptation_engine


def _get_replanner():
    global _replanner
    if _replanner is None:
        from replanner import BlockerDetector
        _replanner = BlockerDetector()
    return _replanner


# ── Tool Retry Configuration ───────────────────────────────────────────────

TOOL_RETRY_CONFIG = {
    "max_retries": 2,
    "backoff_seconds": [1, 3],  # exponential-ish
    "retryable_errors": ["timeout", "rate_limit", "429", "503", "502", "connection"],
}

# Tool alternatives — if primary fails after retries, suggest these to LLM
TOOL_ALTERNATIVES = {
    "web_search": ["web_scrape"],
    "company_research": ["web_search", "enrich_company"],
    "find_contacts": ["web_search", "search_linkedin_prospects"],
    "verify_email": ["web_search"],
    "send_email": ["send_linkedin_message", "send_sms"],
    "post_twitter": ["post_linkedin", "schedule_social_post"],
    "post_linkedin": ["post_twitter", "schedule_social_post"],
    "deploy_to_vercel": ["deploy_to_cloudflare"],
    "deploy_to_cloudflare": ["deploy_to_vercel"],
    "create_meta_ad_campaign": ["create_google_ads_campaign", "create_linkedin_ad_campaign"],
    "create_google_ads_campaign": ["create_meta_ad_campaign", "create_linkedin_ad_campaign"],
    "seo_keyword_research": ["web_search"],
    "generate_image": ["web_search"],
    "publish_to_cms": ["build_landing_page"],
}


class AgentConfig:
    """Configuration for a single agent."""

    def __init__(self, id, label, role, icon, system_prompt_builder, goal_prompt_builder,
                 memory_extractor, tool_categories, tier=Tier.STANDARD, max_iterations=15,
                 model=None, depends_on=None):
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
        self.model = model
        # Dependency graph: list of agent IDs that must complete before this one
        self.depends_on: list[str] = depends_on or []

    def get_tools(self):
        return registry.get_definitions(categories=self.tool_categories)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTION WITH RETRY + FALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

def _is_retryable(error: str) -> bool:
    """Check if a tool error is worth retrying."""
    error_lower = error.lower()
    return any(keyword in error_lower for keyword in TOOL_RETRY_CONFIG["retryable_errors"])


async def _execute_tool_with_retry(tool_name: str, tool_input: dict, call_id: str) -> "ToolResult":
    """Execute a tool with retry logic and exponential backoff."""
    from models import ToolResult as TR

    last_result = None
    max_retries = TOOL_RETRY_CONFIG["max_retries"]
    backoffs = TOOL_RETRY_CONFIG["backoff_seconds"]

    for attempt in range(max_retries + 1):
        result = await registry.execute(tool_name, tool_input, call_id)

        if result.success:
            return result

        last_result = result

        # Check if retryable
        if attempt < max_retries and _is_retryable(result.error or ""):
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            logger.info(f"Tool {tool_name} failed (attempt {attempt + 1}), retrying in {wait}s: {result.error}")
            await asyncio.sleep(wait)
            continue

        # Not retryable or out of retries
        break

    # Enrich error message with alternatives if available
    alternatives = TOOL_ALTERNATIVES.get(tool_name, [])
    if alternatives and last_result and not last_result.success:
        alt_str = ", ".join(alternatives)
        last_result = type(last_result)(
            tool_call_id=last_result.tool_call_id,
            name=last_result.name,
            output=last_result.output,
            error=f"{last_result.error}. Alternative tools you can try: {alt_str}",
            success=False,
        )

    return last_result


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY GATE — Validates agent output before accepting
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_output(agent_id: str, output: str, memory_update: dict) -> dict:
    """
    Lightweight quality gate. Returns {valid: bool, issues: list[str]}.
    No LLM call — pure deterministic checks.
    """
    issues = []

    # Check 1: Output is non-empty
    if not output or len(output.strip()) < 50:
        issues.append("Output is empty or too short (< 50 chars)")

    # Check 2: Memory extraction produced something
    if not memory_update:
        issues.append("Memory extraction produced no data — output may be malformed")

    # Check 3: Agent-specific minimum quality checks
    agent_checks = {
        "prospector": lambda o, m: (
            m.get("prospect_count", 0) >= 1 or "PROSPECT" in o.upper(),
            "No prospects found in output"
        ),
        "outreach": lambda o, m: (
            bool(m.get("email_sequence")) and len(m.get("email_sequence", "")) > 100,
            "Email sequence is missing or too short"
        ),
        "content": lambda o, m: (
            bool(m.get("content_strategy")) and len(m.get("content_strategy", "")) > 100,
            "Content strategy is missing or too short"
        ),
        "sitelaunch": lambda o, m: (
            bool(m.get("site_launch_brief")),
            "Site launch brief not generated"
        ),
    }

    checker = agent_checks.get(agent_id)
    if checker:
        passed, msg = checker(output, memory_update)
        if not passed:
            issues.append(msg)

    return {"valid": len(issues) == 0, "issues": issues}


# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _persist_run_snapshot(agent_id: str, campaign_id: str, campaign: Any):
    """Persist run snapshot to both in-memory and database."""
    try:
        from scoring import scorer
        import db

        adapt = _get_adaptation_engine()
        scores = scorer.score_all(campaign)
        agent_score = scores.get(agent_id, {}).get("score", 0)
        agent_metrics = scores.get(agent_id, {}).get("metrics", {})

        snapshot = adapt.record_run_snapshot(
            agent_id=agent_id, campaign_id=campaign_id,
            score=agent_score, metrics=agent_metrics,
        )

        # Also persist to database
        await db.save_run_snapshot(snapshot)
    except Exception as e:
        logger.debug(f"Snapshot recording skipped for {agent_id}: {e}")


async def _persist_campaign_memory(campaign_id: str, memory: CampaignMemory):
    """Persist campaign memory to database after each agent completes."""
    try:
        import db
        mem_dict = {k: v for k, v in memory.__dict__.items() if not k.startswith("_")}
        await db.update_campaign_memory(campaign_id, mem_dict)
    except Exception as e:
        logger.debug(f"Memory persistence skipped for {campaign_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ENGINE — Production Grade
# ═══════════════════════════════════════════════════════════════════════════════

class AgentEngine:
    """
    Runs a single agent through the ReAct loop with production guarantees:
    1. Plan: Send goal + tools to LLM
    2. Act: Execute tool calls with retry + fallback
    3. Observe: Feed results back to LLM
    4. Validate: Quality gate before accepting output
    5. Persist: Save snapshot + memory to database
    Streams every step as SSE events.
    """

    async def run(self, agent: AgentConfig, memory: CampaignMemory,
                  campaign_id: str = "", tier: Tier = None,
                  campaign: "Campaign | None" = None,
                  trigger_reason: str = "",
                  autonomy_settings: "AutonomySettings | None" = None,
                  ) -> AsyncGenerator[AgentStreamEvent, None]:
        tier = tier or agent.tier
        system = agent.system_prompt_builder(memory)
        goal = agent.goal_prompt_builder(memory)

        # ── Emit agent.started event ──
        try:
            bus = _get_event_bus()
            await bus.agent_started(agent.id, campaign_id)
        except Exception:
            pass

        # ── Load autonomy settings ──
        if autonomy_settings is None:
            try:
                store = _get_autonomy_store()
                autonomy_settings = store.get(campaign_id)
            except Exception:
                autonomy_settings = None

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
        provider_used = ""
        model_used = ""
        tool_failure_count = 0

        while iteration < max_iter:
            iteration += 1
            elapsed = time.time() - start_time

            # ── Graceful timeout: ask LLM to summarize before hard stop ──
            if elapsed > settings.max_agent_runtime - 30:  # 30s warning
                if elapsed > settings.max_agent_runtime:
                    # Hard stop — but extract whatever we have
                    if full_text_output:
                        yield AgentStreamEvent(
                            event=StepType.STATUS, agent_id=agent.id,
                            content=f"Agent timed out after {int(elapsed)}s — returning partial output",
                            status=AgentStatus.DONE,
                        )
                        break  # Fall through to memory extraction + quality gate
                    yield AgentStreamEvent(event=StepType.ERROR, agent_id=agent.id,
                        content=f"Agent timed out after {int(elapsed)}s with no output",
                        status=AgentStatus.ERROR)
                    return

                # Approaching timeout — inject urgency into next LLM call
                if iteration > 1:
                    messages.append({
                        "role": "user",
                        "content": f"[SYSTEM: You have {int(settings.max_agent_runtime - elapsed)}s remaining. "
                                   f"Finish your current task and produce your final output NOW.]",
                    })

            # ── Call LLM ──
            try:
                text_buffer = ""
                tool_calls: list[ToolCall] = []
                _llm_usage: dict[str, int] = {}

                async for chunk in router.complete_stream(
                    messages=messages, system=system,
                    tools=tools if tools else None,
                    tier=tier, max_tokens=settings.default_max_tokens,
                    model_override=agent.model,
                ):
                    if chunk["type"] == "text":
                        text_buffer += chunk["text"]
                        provider_used = chunk.get("provider", provider_used)
                        model_used = chunk.get("model", model_used)
                        yield AgentStreamEvent(
                            event=StepType.THINK, agent_id=agent.id, step=iteration,
                            content=text_buffer, provider=provider_used, model=model_used,
                            status=AgentStatus.EXECUTING,
                        )
                    elif chunk["type"] == "tool_call":
                        tool_calls.append(chunk["tool_call"])
                        provider_used = chunk.get("provider", provider_used)
                        model_used = chunk.get("model", model_used)
                    elif chunk["type"] == "done":
                        provider_used = chunk.get("provider", provider_used)
                        model_used = chunk.get("model", model_used)
                        _llm_usage = chunk.get("usage", {})

            except AllProvidersFailedError as e:
                # Emit failure event
                try:
                    bus = _get_event_bus()
                    await bus.agent_failed(agent.id, campaign_id, str(e))
                except Exception:
                    pass
                yield AgentStreamEvent(event=StepType.ERROR, agent_id=agent.id, step=iteration,
                    content=f"All LLM providers failed: {e}", status=AgentStatus.ERROR)
                return

            # ── Record LLM cost (using provider-reported tokens, fallback to estimate) ──
            if provider_used and model_used and campaign_id:
                try:
                    real_input = _llm_usage.get("input_tokens", 0)
                    real_output = _llm_usage.get("output_tokens", 0)
                    if not real_input:
                        # Fallback: character count / 4 as token estimate
                        real_input = sum(len(str(m.get("content", ""))) for m in messages) // 4
                    if not real_output:
                        real_output = len(text_buffer) // 4
                    cost_tracker.record(
                        campaign_id=campaign_id, agent_id=agent.id,
                        provider=provider_used, model=model_used,
                        input_tokens=real_input,
                        output_tokens=real_output,
                    )
                except Exception:
                    pass

            # ── Handle tool calls with retry + fallback ──
            if tool_calls:
                assistant_content = []
                if text_buffer:
                    assistant_content.append({"type": "text", "text": text_buffer})
                    full_text_output += text_buffer
                for tc in tool_calls:
                    assistant_content.append({
                        "type": "tool_use", "id": tc.id,
                        "name": tc.name, "input": tc.input,
                    })
                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool with retry + autonomy check
                for tc in tool_calls:
                    # ── Autonomy gate: check if tool needs approval ──
                    if autonomy_settings:
                        try:
                            from autonomy import check_tool_approval
                            decision = check_tool_approval(
                                tool_name=tc.name, agent_id=agent.id,
                                settings=autonomy_settings,
                            )
                            if not decision.approved and decision.requires_approval:
                                # Emit approval request event
                                try:
                                    bus = _get_event_bus()
                                    await bus.approval_requested(
                                        agent_id=agent.id, campaign_id=campaign_id,
                                        action_type=decision.approval_type,
                                        content={"tool": tc.name, "input": tc.input,
                                                 "reason": decision.reason},
                                    )
                                except Exception:
                                    pass

                                yield AgentStreamEvent(
                                    event=StepType.STATUS, agent_id=agent.id, step=iteration,
                                    content=f"Approval required: {decision.reason}",
                                    tool_name=tc.name, status=AgentStatus.PAUSED,
                                )
                                # Feed approval-pending result back to LLM
                                messages.append({
                                    "role": "user",
                                    "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                                 "content": f"APPROVAL REQUIRED: {decision.reason}. "
                                                            f"This action has been queued for human approval. "
                                                            f"Continue with other tasks or use alternative approaches."}],
                                })
                                continue

                            elif not decision.approved:
                                # Blocked (not approval-gated, just blocked)
                                messages.append({
                                    "role": "user",
                                    "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                                 "content": f"BLOCKED: {decision.reason}. "
                                                            f"Use an alternative tool or approach."}],
                                })
                                continue
                        except ImportError:
                            logger.error("autonomy module not available — blocking tool %s as a safety default", tc.name)
                            messages.append({
                                "role": "user",
                                "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                             "content": "BLOCKED: Approval system unavailable. Tool execution denied as a safety default."}],
                            })
                            continue

                    # ── Wallet: check budget before executing spending tools ──
                    estimated_cost = TOOL_COST_ESTIMATES.get(tc.name, 0)
                    if estimated_cost > 0 and campaign_id:
                        try:
                            w = _get_wallet()
                            spend_check = await w.request_spend(
                                campaign_id, agent.id, estimated_cost,
                                description=f"{tc.name}({', '.join(f'{k}={v}' for k, v in list(tc.input.items())[:3])})",
                            )
                            if not spend_check.get("approved"):
                                messages.append({
                                    "role": "user",
                                    "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                                 "content": f"BUDGET BLOCKED: {spend_check.get('reason', 'over budget')}. "
                                                            f"Try a free alternative or request budget increase."}],
                                })
                                continue
                        except Exception:
                            pass  # wallet not available, allow execution

                    yield AgentStreamEvent(
                        event=StepType.TOOL_CALL, agent_id=agent.id, step=iteration,
                        content=f"Calling {tc.name}", tool_name=tc.name, tool_input=tc.input,
                        provider=provider_used, model=model_used, status=AgentStatus.TOOL_CALLING,
                    )

                    result = await _execute_tool_with_retry(tc.name, tc.input, tc.id)

                    if not result.success:
                        tool_failure_count += 1

                    # ── Wallet: record actual spend after successful execution ──
                    if result.success and estimated_cost > 0 and campaign_id:
                        try:
                            w = _get_wallet()
                            await w.record_spend(
                                campaign_id, agent.id, estimated_cost,
                                tool=tc.name, description=result.output[:100] if result.output else "",
                            )
                        except Exception:
                            pass

                    yield AgentStreamEvent(
                        event=StepType.TOOL_RESULT, agent_id=agent.id, step=iteration,
                        content=f"{tc.name} → {'OK' if result.success else 'ERROR'}",
                        tool_name=tc.name,
                        tool_output=result.output[:4000] if result.output else result.error,
                        status=AgentStatus.OBSERVING,
                    )

                    # Feed tool result back into conversation
                    messages.append({
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": tc.id,
                                     "content": result.output if result.success else f"Error: {result.error}"}],
                    })

                    # Record step for replanner pattern detection
                    try:
                        replanner = _get_replanner()
                        replanner.record_step(agent.id, campaign_id, {
                            "tool": tc.name, "success": result.success,
                            "error": result.error if not result.success else None,
                        })
                    except Exception:
                        pass

                    # Emit tool execution event
                    try:
                        bus = _get_event_bus()
                        await bus.tool_executed(
                            tool_name=tc.name, agent_id=agent.id,
                            campaign_id=campaign_id, success=result.success,
                            output=result.output[:200] if result.output else "",
                        )
                    except Exception:
                        pass

                continue  # Loop back

            # ── No tool calls = agent done ──
            if text_buffer:
                full_text_output += text_buffer
            break

        # ═══════════════════════════════════════════════════════════════════
        # POST-LOOP: Quality Gate → Memory Extraction → Persistence
        # ═══════════════════════════════════════════════════════════════════

        # ── Extract memory ──
        memory_update = {}
        if full_text_output:
            try:
                memory_update = agent.memory_extractor(full_text_output)
            except Exception as e:
                logger.error(f"Memory extraction failed for {agent.id}: {e}")

        # ── Quality Gate ──
        validation = _validate_output(agent.id, full_text_output, memory_update)
        if not validation["valid"]:
            issues = "; ".join(validation["issues"])
            logger.warning(f"Quality gate flagged {agent.id}: {issues}")
            yield AgentStreamEvent(
                event=StepType.STATUS, agent_id=agent.id,
                content=f"Quality check: {issues}",
                status=AgentStatus.EXECUTING,
            )
            # Don't block — emit warning but still return output
            # Future: retry agent if quality is critically low

        total_ms = int((time.time() - start_time) * 1000)

        yield AgentStreamEvent(
            event=StepType.OUTPUT, agent_id=agent.id, step=iteration,
            content=full_text_output, provider=provider_used,
            status=AgentStatus.DONE, memory_update=memory_update,
        )

        # ── Persist run snapshot + campaign memory ──
        if campaign and campaign_id:
            await _persist_run_snapshot(agent.id, campaign_id, campaign)
            await _persist_campaign_memory(campaign_id, memory)

        # ── Emit agent.completed event ──
        try:
            bus = _get_event_bus()
            await bus.agent_completed(agent.id, campaign_id, memory_update)
        except Exception:
            pass

        logger.info(
            f"Agent {agent.id} done: {iteration} iterations, {total_ms}ms, "
            f"tool_failures={tool_failure_count}, quality={'PASS' if validation['valid'] else 'WARN'}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL CAMPAIGN ORCHESTRATOR — DAG-based execution
# ═══════════════════════════════════════════════════════════════════════════════

# Agent dependency graph: which agents can run in parallel
# Agents with no dependencies run immediately; agents with deps wait
AGENT_DEPENDENCIES = {
    # Campaign layer — mostly sequential
    "prospector": [],
    "outreach": ["prospector"],          # needs prospects
    "content": [],                        # independent
    "social": ["content"],               # needs content strategy
    "ads": [],                           # independent
    "ppc": ["ads"],                      # needs ad foundation
    "cs": ["outreach", "content"],       # needs product context
    "sitelaunch": ["content"],           # needs content + brand
    # Operations — mostly independent
    "legal": [],
    "marketing_expert": [],
    "procurement": [],
    "newsletter": ["content"],
    "formation": [],
    "advisor": [],
    # Back office — mostly independent
    "finance": [],
    "hr": [],
    "sales": ["prospector", "outreach"],  # needs pipeline
    "delivery": ["sales"],
    "analytics_agent": [],
    "tax_strategist": ["finance"],
    "wealth_architect": ["finance", "tax_strategist"],
    # Revenue
    "billing": ["finance"],
    "referral": ["outreach", "cs"],
    "portfolio_ops": [],
    # Everything else — independent
    "competitive_intel": [],
    "client_portal": [],
    "voice_receptionist": [],
    "pr_comms": ["content"],
    "partnerships": [],
    "client_fulfillment": ["delivery"],
    "fullstack_dev": ["sitelaunch"],
    "data_engineer": ["analytics_agent"],
    "hardware_mfg": [],
    "economist": [],
    "governance": [],
    "product_manager": [],
    "enterprise_security": [],
    "knowledge_engine": [],
    "world_model": [],
    "agent_ops": [],
}


async def run_agents_parallel(
    agents: list[AgentConfig],
    memory: CampaignMemory,
    campaign_id: str,
    campaign: "Campaign | None" = None,
    tier: Tier = None,
    event_queue: asyncio.Queue | None = None,
) -> dict[str, str]:
    """
    Run agents respecting dependency graph. Independent agents run concurrently.
    Returns dict of {agent_id: "complete" | "error" | "skipped"}.
    """
    eng = engine
    results: dict[str, str] = {}
    completed: set[str] = set()
    agent_map = {a.id: a for a in agents}
    pending = set(agent_map.keys())

    async def _run_single(agent: AgentConfig):
        """Run one agent, collect events, update shared memory."""
        try:
            async for event in eng.run(
                agent=agent, memory=memory, campaign_id=campaign_id,
                tier=tier, campaign=campaign,
            ):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(memory, k):
                            setattr(memory, k, v)
                if event_queue:
                    await event_queue.put(event)
            results[agent.id] = "complete"
        except Exception as e:
            logger.error(f"Parallel agent {agent.id} failed: {e}", exc_info=True)
            results[agent.id] = "error"
        completed.add(agent.id)

    while pending:
        # Find agents whose dependencies are all satisfied
        ready = []
        for aid in list(pending):
            deps = AGENT_DEPENDENCIES.get(aid, [])
            if all(d in completed or d not in agent_map for d in deps):
                ready.append(aid)

        if not ready:
            # Deadlock — remaining agents have unresolvable deps
            for aid in pending:
                results[aid] = "skipped"
                logger.warning(f"Agent {aid} skipped — unresolvable dependencies")
            break

        # Launch ready agents concurrently
        tasks = []
        for aid in ready:
            pending.discard(aid)
            agent = agent_map[aid]
            tasks.append(asyncio.create_task(_run_single(agent)))

        # Wait for this batch to complete
        await asyncio.gather(*tasks)

    return results


engine = AgentEngine()
