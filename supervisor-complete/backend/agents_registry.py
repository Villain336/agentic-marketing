"""
Agent Registry — Helper utilities for querying and filtering agents.
Provides a cleaner interface on top of the agents module without
requiring a full refactor of the monolithic agents.py file.

Usage:
    from agents_registry import registry
    marketing_agents = registry.get_by_layer("CAMPAIGN_LOOP")
    agent = registry.get("prospector")
"""
from __future__ import annotations
from typing import Optional

from agents import (
    AGENTS, AGENT_MAP, AGENT_ORDER, get_agent,
    CAMPAIGN_LOOP, OPERATIONS_LAYER, BACKOFFICE_LAYER,
    REVENUE_LAYER, DIFFERENTIATION_LAYER, COMMUNICATIONS_LAYER,
    CLIENT_LAYER, BUILDER_LAYER, INDUSTRIAL_LAYER,
    INTELLIGENCE_LAYER, COGNITION_LAYER,
    ONBOARDING_AGENTS, META_AGENTS,
)
from engine import AgentConfig


LAYERS = {
    "CAMPAIGN_LOOP": CAMPAIGN_LOOP,
    "OPERATIONS": OPERATIONS_LAYER,
    "BACKOFFICE": BACKOFFICE_LAYER,
    "REVENUE": REVENUE_LAYER,
    "DIFFERENTIATION": DIFFERENTIATION_LAYER,
    "COMMUNICATIONS": COMMUNICATIONS_LAYER,
    "CLIENT": CLIENT_LAYER,
    "BUILDER": BUILDER_LAYER,
    "INDUSTRIAL": INDUSTRIAL_LAYER,
    "INTELLIGENCE": INTELLIGENCE_LAYER,
    "COGNITION": COGNITION_LAYER,
    "ONBOARDING": ONBOARDING_AGENTS,
    "META": META_AGENTS,
}


class AgentRegistry:
    """Read-only registry for querying agent definitions."""

    @staticmethod
    def get(agent_id: str) -> Optional[AgentConfig]:
        return get_agent(agent_id)

    @staticmethod
    def all() -> list[AgentConfig]:
        return list(AGENTS)

    @staticmethod
    def count() -> int:
        return len(AGENTS)

    @staticmethod
    def ids() -> list[str]:
        return [a.id for a in AGENTS]

    @staticmethod
    def get_by_layer(layer_name: str) -> list[AgentConfig]:
        """Get agents belonging to a specific layer."""
        layer_ids = LAYERS.get(layer_name.upper(), [])
        return [a for a in AGENTS if a.id in layer_ids]

    @staticmethod
    def get_layer(agent_id: str) -> str:
        """Determine which layer an agent belongs to."""
        for layer_name, ids in LAYERS.items():
            if agent_id in ids:
                return layer_name
        return "UNKNOWN"

    @staticmethod
    def get_by_tier(tier_name: str) -> list[AgentConfig]:
        """Get agents filtered by tier (fast/standard/premium)."""
        return [a for a in AGENTS if a.tier.value == tier_name]

    @staticmethod
    def layer_names() -> list[str]:
        return list(LAYERS.keys())

    @staticmethod
    def layer_summary() -> dict[str, int]:
        """Summary of agent count per layer."""
        return {name: len(ids) for name, ids in LAYERS.items()}


registry = AgentRegistry()
