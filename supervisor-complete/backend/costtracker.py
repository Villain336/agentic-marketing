"""
Supervisor Backend — LLM Token Cost Tracker
Tracks inference cost per agent per run. Separate from tool spend (wallet).
"""
from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

logger = logging.getLogger("supervisor.costs")

# Approximate pricing per 1K tokens (as of 2025)
TOKEN_PRICING = {
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.001, "output": 0.005},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    # Google
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.0-flash-lite": {"input": 0.00005, "output": 0.0002},
}

# Fallback pricing for unknown models
DEFAULT_PRICING = {"input": 0.003, "output": 0.015}


class CostEntry:
    """A single LLM call cost record."""

    def __init__(self, campaign_id: str, agent_id: str, provider: str,
                 model: str, input_tokens: int, output_tokens: int):
        self.campaign_id = campaign_id
        self.agent_id = agent_id
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.timestamp = datetime.utcnow()

        pricing = TOKEN_PRICING.get(model, DEFAULT_PRICING)
        self.input_cost = (input_tokens / 1000) * pricing["input"]
        self.output_cost = (output_tokens / 1000) * pricing["output"]
        self.total_cost = self.input_cost + self.output_cost


class CostTracker:
    """Tracks LLM inference costs per campaign and agent."""

    def __init__(self):
        # campaign_id -> list of cost entries
        self._entries: dict[str, list[CostEntry]] = defaultdict(list)

    def record(self, campaign_id: str, agent_id: str, provider: str,
               model: str, input_tokens: int, output_tokens: int) -> CostEntry:
        """Record an LLM call cost."""
        entry = CostEntry(campaign_id, agent_id, provider, model,
                          input_tokens, output_tokens)
        self._entries[campaign_id].append(entry)
        return entry

    def get_campaign_cost(self, campaign_id: str) -> dict[str, Any]:
        """Get total costs for a campaign, broken down by agent."""
        entries = self._entries.get(campaign_id, [])
        if not entries:
            return {"total_cost": 0, "total_tokens": 0, "agents": {}}

        total_cost = sum(e.total_cost for e in entries)
        total_input = sum(e.input_tokens for e in entries)
        total_output = sum(e.output_tokens for e in entries)

        # Per-agent breakdown
        agent_costs: dict[str, dict] = defaultdict(lambda: {
            "cost": 0, "input_tokens": 0, "output_tokens": 0, "calls": 0,
        })
        for e in entries:
            agent_costs[e.agent_id]["cost"] += e.total_cost
            agent_costs[e.agent_id]["input_tokens"] += e.input_tokens
            agent_costs[e.agent_id]["output_tokens"] += e.output_tokens
            agent_costs[e.agent_id]["calls"] += 1

        # Per-provider breakdown
        provider_costs: dict[str, float] = defaultdict(float)
        for e in entries:
            provider_costs[e.provider] += e.total_cost

        return {
            "total_cost": round(total_cost, 4),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_calls": len(entries),
            "agents": {k: {**v, "cost": round(v["cost"], 4)} for k, v in agent_costs.items()},
            "providers": {k: round(v, 4) for k, v in provider_costs.items()},
        }

    def get_agent_cost(self, campaign_id: str, agent_id: str) -> dict[str, Any]:
        """Get costs for a specific agent in a campaign."""
        entries = [e for e in self._entries.get(campaign_id, [])
                   if e.agent_id == agent_id]
        if not entries:
            return {"cost": 0, "calls": 0, "tokens": 0}

        return {
            "cost": round(sum(e.total_cost for e in entries), 4),
            "calls": len(entries),
            "input_tokens": sum(e.input_tokens for e in entries),
            "output_tokens": sum(e.output_tokens for e in entries),
            "models_used": list(set(e.model for e in entries)),
        }

    def get_global_stats(self) -> dict[str, Any]:
        """Get global cost stats across all campaigns."""
        all_entries = [e for entries in self._entries.values() for e in entries]
        if not all_entries:
            return {"total_cost": 0, "campaigns": 0, "total_calls": 0}

        return {
            "total_cost": round(sum(e.total_cost for e in all_entries), 4),
            "campaigns": len(self._entries),
            "total_calls": len(all_entries),
            "total_tokens": sum(e.input_tokens + e.output_tokens for e in all_entries),
            "avg_cost_per_call": round(sum(e.total_cost for e in all_entries) / len(all_entries), 4),
        }


# Singleton
cost_tracker = CostTracker()
