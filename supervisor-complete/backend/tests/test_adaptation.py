"""Tests for the adaptation engine."""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from adaptation import (
    AdaptationEngine,
    AdaptiveContext,
    PerformanceFeedback,
    LearnedStrategy,
    STRATEGY_RULES,
    _run_snapshots,
)
from models import Campaign, CampaignMemory, BusinessProfile


def _make_campaign(**overrides) -> Campaign:
    biz = BusinessProfile(
        name="Test Co", service="SaaS", icp="B2B", geography="US", goal="grow",
        entity_type="llc", state_of_formation="Delaware",
        founder_title="Managing Member", industry="marketing agency",
    )
    mem = CampaignMemory(
        business=biz,
        email_sequence="Subject: hello",
        content_strategy="blog weekly",
        social_calendar="Mon: LinkedIn",
        legal_playbook="privacy, terms, compliance, contract",
        gtm_strategy="PLG funnel",
    )
    return Campaign(id="adapt-001", user_id="u1", memory=mem, **overrides)


# ── build_context ────────────────────────────────────────────────────────────

class TestBuildContext:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = AdaptationEngine()
        self.campaign = _make_campaign()

    async def test_returns_adaptive_context(self):
        with patch("scoring.scorer") as mock_scorer, \
             patch("genome.genome") as mock_genome:
            mock_scorer.score_all.return_value = {}
            mock_genome.get_live_intelligence.return_value = {"matches": 0}
            ctx = await self.engine.build_context("outreach", self.campaign)
        assert isinstance(ctx, AdaptiveContext)
        assert ctx.agent_id == "outreach"
        assert ctx.campaign_id == "adapt-001"

    async def test_context_includes_performance_when_scored(self):
        with patch("scoring.scorer") as mock_scorer, \
             patch("genome.genome") as mock_genome:
            mock_scorer.score_all.return_value = {
                "outreach": {
                    "score": 45, "grade": "D",
                    "reasoning": "Low reply rate", "metrics": {},
                }
            }
            mock_genome.get_live_intelligence.return_value = {"matches": 0}
            ctx = await self.engine.build_context("outreach", self.campaign)
        assert ctx.performance is not None
        assert ctx.performance.grade == "D"
        assert ctx.performance.score == 45


# ── _compute_trend ───────────────────────────────────────────────────────────

class TestComputeTrend:
    def setup_method(self):
        self.engine = AdaptationEngine()
        # Clean snapshot state
        _run_snapshots.clear()

    def test_unknown_with_no_data(self):
        assert self.engine._compute_trend("c1", "outreach") == "unknown"

    def test_unknown_with_one_snapshot(self):
        _run_snapshots["c1:outreach"] = [{"score": 50}]
        assert self.engine._compute_trend("c1", "outreach") == "unknown"

    def test_improving_with_two_points(self):
        _run_snapshots["c1:outreach"] = [{"score": 30}, {"score": 80}]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "improving"

    def test_declining_with_two_points(self):
        _run_snapshots["c1:outreach"] = [{"score": 90}, {"score": 20}]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "declining"

    def test_stable_with_similar_scores(self):
        _run_snapshots["c1:outreach"] = [{"score": 50}, {"score": 52}]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "stable"

    def test_improving_with_many_points(self):
        # Clearly upward trend
        _run_snapshots["c1:outreach"] = [
            {"score": 20}, {"score": 30}, {"score": 40},
            {"score": 50}, {"score": 65}, {"score": 80},
        ]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "improving"

    def test_declining_with_many_points(self):
        _run_snapshots["c1:outreach"] = [
            {"score": 90}, {"score": 80}, {"score": 65},
            {"score": 50}, {"score": 35}, {"score": 20},
        ]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "declining"

    def test_stable_with_flat_scores(self):
        _run_snapshots["c1:outreach"] = [
            {"score": 50}, {"score": 51}, {"score": 50},
            {"score": 49}, {"score": 50}, {"score": 51},
        ]
        trend = self.engine._compute_trend("c1", "outreach")
        assert trend == "stable"


# ── Weighted linear regression correctness ───────────────────────────────────

class TestWeightedRegression:
    def setup_method(self):
        self.engine = AdaptationEngine()
        _run_snapshots.clear()

    def test_perfect_upward_line(self):
        # Scores 0, 10, 20, 30, 40 → slope = 10, clearly > 2
        _run_snapshots["c1:a"] = [{"score": s} for s in [0, 10, 20, 30, 40]]
        assert self.engine._compute_trend("c1", "a") == "improving"

    def test_perfect_downward_line(self):
        _run_snapshots["c1:a"] = [{"score": s} for s in [40, 30, 20, 10, 0]]
        assert self.engine._compute_trend("c1", "a") == "declining"

    def test_constant_line(self):
        _run_snapshots["c1:a"] = [{"score": 50} for _ in range(5)]
        assert self.engine._compute_trend("c1", "a") == "stable"


# ── render_prompt_block ──────────────────────────────────────────────────────

class TestRenderPromptBlock:
    def setup_method(self):
        self.engine = AdaptationEngine()

    def test_empty_context_returns_empty(self):
        ctx = AdaptiveContext(agent_id="outreach", campaign_id="c1")
        assert self.engine.render_prompt_block(ctx) == ""

    def test_with_performance_returns_nonempty(self):
        ctx = AdaptiveContext(
            agent_id="outreach", campaign_id="c1",
            performance=PerformanceFeedback(
                agent_id="outreach", grade="B", score=75,
                reasoning="Decent reply rate",
                key_metrics={"reply_rate": 3.5, "open_rate": 40.0},
            ),
        )
        block = self.engine.render_prompt_block(ctx)
        assert len(block) > 0
        assert "ADAPTIVE INTELLIGENCE" in block
        assert "Grade: B" in block

    def test_with_strategies(self):
        ctx = AdaptiveContext(
            agent_id="outreach", campaign_id="c1",
            strategies=[
                LearnedStrategy(
                    source="sensing", directive="Improve subject lines",
                    confidence=0.9,
                ),
            ],
        )
        block = self.engine.render_prompt_block(ctx)
        assert "STRATEGIES TO APPLY" in block
        assert "Improve subject lines" in block

    def test_directive_on_poor_grade(self):
        ctx = AdaptiveContext(
            agent_id="outreach", campaign_id="c1",
            performance=PerformanceFeedback(
                agent_id="outreach", grade="F", score=10,
                reasoning="Very poor",
            ),
        )
        block = self.engine.render_prompt_block(ctx)
        assert "DIRECTIVE" in block
        assert "underperformed" in block


# ── Strategy rules ───────────────────────────────────────────────────────────

class TestStrategyRules:
    def setup_method(self):
        self.engine = AdaptationEngine()

    def test_outreach_low_reply_rate_fires(self):
        perf = PerformanceFeedback(
            agent_id="outreach", grade="D", score=30,
            reasoning="bad", key_metrics={"reply_rate": 0.5, "open_rate": 25.0},
        )
        strategies = self.engine._derive_strategies("outreach", perf)
        directives = [s.directive for s in strategies]
        assert any("Reply rate" in d for d in directives)

    def test_outreach_low_open_rate_fires(self):
        perf = PerformanceFeedback(
            agent_id="outreach", grade="D", score=30,
            reasoning="bad", key_metrics={"reply_rate": 5.0, "open_rate": 15.0},
        )
        strategies = self.engine._derive_strategies("outreach", perf)
        directives = [s.directive for s in strategies]
        assert any("Open rate" in d for d in directives)

    def test_content_high_bounce_fires(self):
        perf = PerformanceFeedback(
            agent_id="content", grade="C", score=40,
            reasoning="bad",
            key_metrics={"bounce_rate": 75.0, "sessions": 200, "conversion_rate": 0.5},
        )
        strategies = self.engine._derive_strategies("content", perf)
        directives = [s.directive for s in strategies]
        assert any("Bounce rate" in d for d in directives)

    def test_no_rules_fire_for_good_metrics(self):
        perf = PerformanceFeedback(
            agent_id="outreach", grade="A", score=95,
            reasoning="great",
            key_metrics={"reply_rate": 10.0, "open_rate": 60.0, "bounce_rate": 1.0},
        )
        strategies = self.engine._derive_strategies("outreach", perf)
        assert len(strategies) == 0
