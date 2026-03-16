"""
Supervisor Backend — Agent Lifecycle Management
A/B testing agents, spawning specialist variants, dissolving underperformers,
and promoting high performers to default status.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from models import Campaign, Tier
from scoring import scorer

logger = logging.getLogger("supervisor.lifecycle")


class AgentVariant:
    """A variant of an agent for A/B testing different prompts or strategies."""

    def __init__(
        self,
        variant_id: str,
        agent_id: str,
        name: str,
        system_prompt_override: str = "",
        goal_prompt_override: str = "",
        tool_categories_override: list[str] | None = None,
        tier_override: Tier | None = None,
    ):
        self.variant_id = variant_id
        self.agent_id = agent_id
        self.name = name
        self.system_prompt_override = system_prompt_override
        self.goal_prompt_override = goal_prompt_override
        self.tool_categories_override = tool_categories_override
        self.tier_override = tier_override
        self.created_at = datetime.utcnow()
        self.runs: int = 0
        self.total_score: float = 0.0
        self.promoted: bool = False
        self.dissolved: bool = False

    @property
    def avg_score(self) -> float:
        return self.total_score / self.runs if self.runs > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "runs": self.runs,
            "avg_score": round(self.avg_score, 1),
            "promoted": self.promoted,
            "dissolved": self.dissolved,
            "created_at": self.created_at.isoformat(),
        }


class ABTest:
    """An active A/B test between agent variants."""

    def __init__(
        self,
        test_id: str,
        agent_id: str,
        variants: list[AgentVariant],
        min_runs_per_variant: int = 3,
        auto_promote: bool = True,
    ):
        self.test_id = test_id
        self.agent_id = agent_id
        self.variants = {v.variant_id: v for v in variants}
        self.min_runs_per_variant = min_runs_per_variant
        self.auto_promote = auto_promote
        self.status = "running"  # running, complete, cancelled
        self.winner_id: str | None = None
        self.created_at = datetime.utcnow()

    def record_result(self, variant_id: str, score: float) -> None:
        variant = self.variants.get(variant_id)
        if variant and not variant.dissolved:
            variant.runs += 1
            variant.total_score += score

    def check_winner(self) -> Optional[str]:
        """Check if we have enough data to declare a winner."""
        eligible = [
            v for v in self.variants.values()
            if v.runs >= self.min_runs_per_variant and not v.dissolved
        ]
        if len(eligible) < 2:
            return None

        # Sort by average score
        eligible.sort(key=lambda v: v.avg_score, reverse=True)
        best = eligible[0]
        second = eligible[1]

        # Need at least 10% improvement to declare winner
        if best.avg_score > 0 and (best.avg_score - second.avg_score) / best.avg_score >= 0.10:
            self.winner_id = best.variant_id
            self.status = "complete"
            if self.auto_promote:
                best.promoted = True
            return best.variant_id

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "variants": [v.to_dict() for v in self.variants.values()],
            "winner_id": self.winner_id,
            "created_at": self.created_at.isoformat(),
        }


class LifecycleManager:
    """Manages agent spawning, A/B testing, dissolution, and promotion."""

    def __init__(self):
        self._tests: dict[str, ABTest] = {}
        self._variants: dict[str, AgentVariant] = {}
        self._dissolution_log: list[dict] = []
        self._promotion_log: list[dict] = []

    # ── A/B Testing ──────────────────────────────────────────────────────

    def create_ab_test(
        self,
        agent_id: str,
        variant_configs: list[dict[str, Any]],
        min_runs: int = 3,
        auto_promote: bool = True,
    ) -> ABTest:
        """Create an A/B test with multiple agent variants."""
        variants = []
        for cfg in variant_configs:
            vid = str(uuid.uuid4())[:8]
            variant = AgentVariant(
                variant_id=vid,
                agent_id=agent_id,
                name=cfg.get("name", f"variant-{vid}"),
                system_prompt_override=cfg.get("system_prompt", ""),
                goal_prompt_override=cfg.get("goal_prompt", ""),
                tool_categories_override=cfg.get("tool_categories"),
                tier_override=Tier(cfg["tier"]) if "tier" in cfg else None,
            )
            variants.append(variant)
            self._variants[vid] = variant

        test = ABTest(
            test_id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            variants=variants,
            min_runs_per_variant=min_runs,
            auto_promote=auto_promote,
        )
        self._tests[test.test_id] = test
        logger.info(f"Created A/B test {test.test_id} for {agent_id} with {len(variants)} variants")
        return test

    def record_test_result(self, test_id: str, variant_id: str, score: float) -> Optional[str]:
        """Record a variant run result. Returns winner_id if test concluded."""
        test = self._tests.get(test_id)
        if not test or test.status != "running":
            return None

        test.record_result(variant_id, score)
        winner = test.check_winner()
        if winner:
            logger.info(f"A/B test {test_id} complete — winner: {winner}")
        return winner

    def get_test(self, test_id: str) -> Optional[dict]:
        test = self._tests.get(test_id)
        return test.to_dict() if test else None

    def list_tests(self, agent_id: str = "") -> list[dict]:
        tests = self._tests.values()
        if agent_id:
            tests = [t for t in tests if t.agent_id == agent_id]
        return [t.to_dict() for t in tests]

    # ── Agent Health & Dissolution ───────────────────────────────────────

    def evaluate_health(self, campaign: Campaign) -> dict[str, Any]:
        """Evaluate all agents in a campaign and flag underperformers."""
        scores = scorer.score_all(campaign)

        healthy = []
        warning = []
        critical = []

        for agent_id, data in scores.items():
            grade = data.get("grade", "F")
            entry = {"agent_id": agent_id, "grade": grade, "score": data.get("score", 0)}

            if grade in ("A+", "A", "A-", "B+", "B", "B-"):
                healthy.append(entry)
            elif grade in ("C+", "C", "C-"):
                warning.append(entry)
            else:
                critical.append(entry)

        return {
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "total_agents": len(scores),
            "health_pct": round(len(healthy) / max(len(scores), 1) * 100, 1),
        }

    def recommend_dissolution(self, campaign: Campaign) -> list[dict]:
        """Recommend agents that should be dissolved (replaced or removed)."""
        health = self.evaluate_health(campaign)
        recommendations = []

        for agent in health["critical"]:
            recommendations.append({
                "agent_id": agent["agent_id"],
                "grade": agent["grade"],
                "action": "dissolve_and_respawn",
                "reason": f"Grade {agent['grade']} — agent underperforming. Recommend respawning with modified strategy.",
            })

        for agent in health["warning"]:
            recommendations.append({
                "agent_id": agent["agent_id"],
                "grade": agent["grade"],
                "action": "ab_test",
                "reason": f"Grade {agent['grade']} — agent borderline. Recommend A/B testing alternate strategies.",
            })

        return recommendations

    def dissolve_agent(self, agent_id: str, campaign_id: str, reason: str) -> dict:
        """Mark an agent as dissolved for a campaign."""
        entry = {
            "agent_id": agent_id,
            "campaign_id": campaign_id,
            "reason": reason,
            "dissolved_at": datetime.utcnow().isoformat(),
        }
        self._dissolution_log.append(entry)
        logger.info(f"Dissolved agent {agent_id} in campaign {campaign_id}: {reason}")
        return entry

    def promote_variant(self, variant_id: str, reason: str) -> dict:
        """Promote a winning variant to become the default."""
        variant = self._variants.get(variant_id)
        if not variant:
            return {"error": "Variant not found"}

        variant.promoted = True
        entry = {
            "variant_id": variant_id,
            "agent_id": variant.agent_id,
            "name": variant.name,
            "avg_score": variant.avg_score,
            "reason": reason,
            "promoted_at": datetime.utcnow().isoformat(),
        }
        self._promotion_log.append(entry)
        logger.info(f"Promoted variant {variant_id} ({variant.name}) for agent {variant.agent_id}")
        return entry

    # ── Status ──────────────────────────────────────────────────────────

    def get_dissolution_log(self, campaign_id: str = "") -> list[dict]:
        if campaign_id:
            return [d for d in self._dissolution_log if d["campaign_id"] == campaign_id]
        return self._dissolution_log

    def get_promotion_log(self) -> list[dict]:
        return self._promotion_log


# Singleton
lifecycle = LifecycleManager()
