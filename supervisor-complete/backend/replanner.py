"""
Omni OS Backend — Dynamic Mid-Execution Re-Planning
Agents detect blockers during execution and adapt strategy in real-time.
Competes with Devin's dynamic re-planning and Manus's autonomous recovery.
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.replanner")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BlockerDetection(BaseModel):
    """A detected blocker during agent execution."""
    id: str = Field(default_factory=lambda: f"blk_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    agent_id: str
    campaign_id: str = ""
    iteration: int = 0
    blocker_type: str = ""      # tool_failure | rate_limit | data_missing | quality_low | budget_exceeded
    description: str = ""
    failed_tool: str = ""
    error_message: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class ReplanAction(BaseModel):
    """An action taken by the replanner to recover from a blocker."""
    blocker_id: str
    strategy: str = ""          # retry_alternate | skip_step | substitute_tool | reduce_scope | escalate
    description: str = ""
    new_instructions: str = ""
    applied_at: datetime = Field(default_factory=datetime.utcnow)


class ReplanHistory(BaseModel):
    """Full history of replanning events for an agent run."""
    agent_id: str
    campaign_id: str
    blockers: list[BlockerDetection] = []
    actions: list[ReplanAction] = []
    total_replans: int = 0
    final_outcome: str = ""     # recovered | escalated | failed


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class BlockerDetector:
    """
    Monitors agent execution for patterns that indicate the agent is stuck.
    Triggers re-planning when blockers are detected.
    """

    # Patterns that suggest the agent is stuck
    STUCK_PATTERNS = {
        "repeated_failure": {"threshold": 2, "window_steps": 3},   # Same tool fails 2x in 3 steps
        "no_progress": {"threshold": 3, "window_steps": 5},        # 3 steps with no memory update
        "rate_limited": {"threshold": 1},                           # Any rate limit hit
        "budget_exceeded": {"threshold": 1},                       # Budget check failure
        "quality_gate_fail": {"threshold": 2},                     # Gauntlet rejection 2x
    }

    # Tool alternatives — if one fails, try these
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

    def __init__(self):
        self._run_history: dict[str, list[dict]] = {}  # run_key -> step history

    def _run_key(self, agent_id: str, campaign_id: str) -> str:
        return f"{campaign_id}:{agent_id}"

    def record_step(self, agent_id: str, campaign_id: str, step: dict):
        """Record an execution step for pattern analysis."""
        key = self._run_key(agent_id, campaign_id)
        if key not in self._run_history:
            self._run_history[key] = []
        self._run_history[key].append({**step, "timestamp": time.time()})

    def detect_blocker(self, agent_id: str, campaign_id: str,
                       tool_name: str = "", error: str = "",
                       step_type: str = "") -> Optional[BlockerDetection]:
        """
        Analyze recent execution history to detect if agent is blocked.
        Returns BlockerDetection if a blocker is found, None otherwise.
        """
        key = self._run_key(agent_id, campaign_id)
        history = self._run_history.get(key, [])

        # Check: repeated tool failure
        if error and tool_name:
            recent_failures = [
                s for s in history[-5:]
                if s.get("tool") == tool_name and s.get("error")
            ]
            if len(recent_failures) >= self.STUCK_PATTERNS["repeated_failure"]["threshold"]:
                return BlockerDetection(
                    agent_id=agent_id, campaign_id=campaign_id,
                    blocker_type="tool_failure",
                    description=f"Tool {tool_name} failed {len(recent_failures)} times",
                    failed_tool=tool_name, error_message=error,
                    iteration=len(history),
                )

        # Check: rate limiting
        if "rate" in error.lower() or "429" in error:
            return BlockerDetection(
                agent_id=agent_id, campaign_id=campaign_id,
                blocker_type="rate_limit",
                description=f"Rate limited on {tool_name}",
                failed_tool=tool_name, error_message=error,
                iteration=len(history),
            )

        # Check: no progress (many steps, no tool calls succeeding)
        recent = history[-5:]
        if len(recent) >= 5:
            success_count = sum(1 for s in recent if s.get("success"))
            if success_count == 0:
                return BlockerDetection(
                    agent_id=agent_id, campaign_id=campaign_id,
                    blocker_type="no_progress",
                    description="No successful actions in last 5 steps",
                    iteration=len(history),
                )

        return None

    def clear_history(self, agent_id: str, campaign_id: str):
        key = self._run_key(agent_id, campaign_id)
        self._run_history.pop(key, None)


# ═══════════════════════════════════════════════════════════════════════════════
# RE-PLANNING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class Replanner:
    """
    When a blocker is detected, the Replanner generates recovery instructions
    that get injected into the agent's next LLM call.
    """

    MAX_REPLANS_PER_RUN = 3  # Don't let agents replan forever

    def __init__(self):
        self.detector = BlockerDetector()
        self._histories: dict[str, ReplanHistory] = {}  # run_key -> history

    def _run_key(self, agent_id: str, campaign_id: str) -> str:
        return f"{campaign_id}:{agent_id}"

    def record_step(self, agent_id: str, campaign_id: str,
                    tool_name: str = "", success: bool = True,
                    error: str = "", output: str = ""):
        """Record a step and check for blockers."""
        self.detector.record_step(agent_id, campaign_id, {
            "tool": tool_name, "success": success,
            "error": error, "output_len": len(output or ""),
        })

    def check_and_replan(self, agent_id: str, campaign_id: str,
                         tool_name: str = "", error: str = "") -> Optional[str]:
        """
        Check if agent is blocked and generate re-planning instructions.
        Returns injection text for the agent's system prompt, or None.
        """
        key = self._run_key(agent_id, campaign_id)

        # Initialize history
        if key not in self._histories:
            self._histories[key] = ReplanHistory(agent_id=agent_id, campaign_id=campaign_id)

        history = self._histories[key]

        # Don't exceed replan limit
        if history.total_replans >= self.MAX_REPLANS_PER_RUN:
            return None

        # Detect blocker
        blocker = self.detector.detect_blocker(
            agent_id, campaign_id, tool_name, error,
        )

        if not blocker:
            return None

        # Generate recovery strategy
        action = self._generate_recovery(blocker)

        # Record
        history.blockers.append(blocker)
        history.actions.append(action)
        history.total_replans += 1

        logger.info(
            f"Replan #{history.total_replans} for {agent_id}: "
            f"{blocker.blocker_type} → {action.strategy}"
        )

        return action.new_instructions

    def _generate_recovery(self, blocker: BlockerDetection) -> ReplanAction:
        """Generate a recovery strategy based on blocker type."""

        if blocker.blocker_type == "tool_failure":
            alternatives = BlockerDetector.TOOL_ALTERNATIVES.get(blocker.failed_tool, [])
            if alternatives:
                alt_list = ", ".join(alternatives)
                return ReplanAction(
                    blocker_id=blocker.id,
                    strategy="substitute_tool",
                    description=f"Switching from {blocker.failed_tool} to alternatives",
                    new_instructions=(
                        f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                        f"The tool '{blocker.failed_tool}' has failed repeatedly. "
                        f"DO NOT use it again. Instead, use one of these alternatives: {alt_list}. "
                        f"Adapt your approach to work with the available tools. "
                        f"If none of the alternatives work, skip this step and move on to the next part of your task."
                    ),
                )
            else:
                return ReplanAction(
                    blocker_id=blocker.id,
                    strategy="skip_step",
                    description=f"No alternatives for {blocker.failed_tool}, skipping",
                    new_instructions=(
                        f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                        f"The tool '{blocker.failed_tool}' is unavailable. "
                        f"Skip any tasks that require this tool and focus on completing "
                        f"the rest of your objectives with the tools you have."
                    ),
                )

        elif blocker.blocker_type == "rate_limit":
            return ReplanAction(
                blocker_id=blocker.id,
                strategy="reduce_scope",
                description="Rate limited — reducing scope",
                new_instructions=(
                    f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                    f"You've been rate-limited on '{blocker.failed_tool}'. "
                    f"Reduce your usage of external APIs. Focus on generating your "
                    f"best output with the data you already have. Do NOT retry the "
                    f"rate-limited tool. Use web_search as a fallback if needed."
                ),
            )

        elif blocker.blocker_type == "no_progress":
            return ReplanAction(
                blocker_id=blocker.id,
                strategy="reduce_scope",
                description="No progress detected — simplifying approach",
                new_instructions=(
                    f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                    f"You appear to be stuck with no successful actions in recent steps. "
                    f"STOP your current approach. Take a simpler path:\n"
                    f"1. Use only the most basic tools (web_search, store_data)\n"
                    f"2. Produce your output based on your training knowledge\n"
                    f"3. Clearly note which parts could not be verified with live data\n"
                    f"Deliver SOMETHING useful rather than continuing to fail."
                ),
            )

        elif blocker.blocker_type == "budget_exceeded":
            return ReplanAction(
                blocker_id=blocker.id,
                strategy="escalate",
                description="Budget exceeded — escalating to user",
                new_instructions=(
                    f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                    f"The budget for this task has been exceeded. "
                    f"Complete your current work WITHOUT making any more paid API calls. "
                    f"Summarize what you've accomplished so far and what remains to be done."
                ),
            )

        # Default fallback
        return ReplanAction(
            blocker_id=blocker.id,
            strategy="reduce_scope",
            description="Generic recovery",
            new_instructions=(
                f"\n\n[REPLAN] IMPORTANT RE-PLANNING NOTICE:\n"
                f"An issue was detected: {blocker.description}. "
                f"Adapt your approach and continue with available resources."
            ),
        )

    def get_history(self, agent_id: str, campaign_id: str) -> Optional[ReplanHistory]:
        key = self._run_key(agent_id, campaign_id)
        return self._histories.get(key)

    def get_stats(self) -> dict:
        """Get replanning statistics across all runs."""
        total_replans = sum(h.total_replans for h in self._histories.values())
        strategies = {}
        for h in self._histories.values():
            for a in h.actions:
                strategies[a.strategy] = strategies.get(a.strategy, 0) + 1
        return {
            "total_runs_with_replans": len(self._histories),
            "total_replans": total_replans,
            "strategies_used": strategies,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

replanner = Replanner()
