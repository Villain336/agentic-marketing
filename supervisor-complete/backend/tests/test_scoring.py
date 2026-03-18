"""Tests for the scoring engine."""
from __future__ import annotations

import pytest

from scoring import AgentScorer, _to_grade, GRADE_THRESHOLDS


# ── Grade mapping ────────────────────────────────────────────────────────────

class TestGradeMapping:
    def test_grade_a_plus(self):
        assert _to_grade(95) == "A+"
        assert _to_grade(100) == "A+"

    def test_grade_a(self):
        assert _to_grade(90) == "A"
        assert _to_grade(94) == "A"

    def test_grade_b(self):
        assert _to_grade(75) == "B"
        assert _to_grade(79) == "B"

    def test_grade_c(self):
        assert _to_grade(55) == "C"

    def test_grade_d(self):
        assert _to_grade(40) == "D"
        assert _to_grade(49) == "D"

    def test_grade_f(self):
        assert _to_grade(0) == "F"
        assert _to_grade(39) == "F"

    def test_grade_f_negative(self):
        assert _to_grade(-5) == "F"


# ── Individual scorer bounds ─────────────────────────────────────────────────

class TestScoreBounds:
    """Every scorer must return a score in [0, 100]."""

    def test_score_all_returns_dict_with_expected_keys(self, campaign):
        scorer = AgentScorer()
        results = scorer.score_all(campaign)
        assert isinstance(results, dict)
        # At minimum, these core agents must appear
        for key in ("prospector", "outreach", "content", "social", "ads",
                     "cs", "sitelaunch", "legal", "marketing_expert"):
            assert key in results, f"Missing agent key: {key}"
            assert "score" in results[key]
            assert "grade" in results[key]
            assert "reasoning" in results[key]

    def test_all_scores_in_range(self, campaign):
        scorer = AgentScorer()
        results = scorer.score_all(campaign)
        for agent_id, data in results.items():
            score = data["score"]
            assert 0 <= score <= 100, f"{agent_id} score {score} out of range"

    def test_all_grades_valid(self, campaign):
        valid_grades = {g for _, g in GRADE_THRESHOLDS} | {"—"}
        scorer = AgentScorer()
        results = scorer.score_all(campaign)
        for agent_id, data in results.items():
            assert data["grade"] in valid_grades, f"{agent_id} has invalid grade {data['grade']}"


# ── Legal scorer specifics ───────────────────────────────────────────────────

class TestScoreLegal:
    def test_legal_with_real_playbook(self, campaign):
        scorer = AgentScorer()
        metrics = getattr(campaign, "_metrics", {})
        result = scorer._score_legal(campaign, metrics)
        assert result["score"] > 35, "Real playbook with keywords should score above base"
        assert result["metrics"]["sections_covered"] > 0

    def test_legal_with_empty_playbook(self, campaign):
        campaign.memory.legal_playbook = ""
        scorer = AgentScorer()
        metrics = getattr(campaign, "_metrics", {})
        result = scorer._score_legal(campaign, metrics)
        assert result["score"] == 0
        assert "No legal playbook" in result["reasoning"]

    def test_legal_with_short_playbook(self, campaign):
        campaign.memory.legal_playbook = "privacy terms"
        scorer = AgentScorer()
        metrics = getattr(campaign, "_metrics", {})
        result = scorer._score_legal(campaign, metrics)
        # Base 35 + some depth + some coverage
        assert result["score"] >= 35
        assert result["metrics"]["sections_covered"] >= 2


# ── Sitelaunch scorer ────────────────────────────────────────────────────────

class TestScoreSitelaunch:
    def test_no_brief(self, campaign):
        campaign.memory.site_launch_brief = ""
        scorer = AgentScorer()
        result = scorer._score_sitelaunch(campaign, {})
        assert result["score"] == 0

    def test_brief_only_no_metrics(self, campaign):
        scorer = AgentScorer()
        result = scorer._score_sitelaunch(campaign, {})
        assert result["score"] == 30

    def test_brief_with_site_metrics(self, campaign):
        metrics = {
            "site_metrics": {
                "sessions": 200,
                "bounce_rate": 40.0,
                "conversion_rate": 3.0,
            }
        }
        scorer = AgentScorer()
        result = scorer._score_sitelaunch(campaign, metrics)
        # base 30 + traffic + bounce + conversion
        assert result["score"] > 30
        assert result["score"] <= 100

    def test_high_bounce_low_conversion(self, campaign):
        metrics = {
            "site_metrics": {
                "sessions": 500,
                "bounce_rate": 95.0,
                "conversion_rate": 0.1,
            }
        }
        scorer = AgentScorer()
        result = scorer._score_sitelaunch(campaign, metrics)
        # Still above base but bounce kills quality score
        assert result["score"] >= 30


# ── Outreach scorer ──────────────────────────────────────────────────────────

class TestScoreOutreach:
    def test_no_sequence(self, campaign):
        campaign.memory.email_sequence = ""
        scorer = AgentScorer()
        result = scorer._score_outreach(campaign, {})
        assert result["score"] == 0

    def test_sequence_no_delivery_data(self, campaign):
        scorer = AgentScorer()
        result = scorer._score_outreach(campaign, {})
        assert result["score"] == 30  # has sequence, no data

    def test_with_email_metrics(self, campaign):
        metrics = {
            "email_metrics": {
                "delivered": 100,
                "open_rate": 45.0,
                "reply_rate": 5.0,
            }
        }
        scorer = AgentScorer()
        result = scorer._score_outreach(campaign, metrics)
        assert result["score"] > 30
