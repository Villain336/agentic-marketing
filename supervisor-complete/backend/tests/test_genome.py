"""Tests for the campaign genome engine."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from genome import CampaignGenome, CampaignDNA
from models import Campaign, CampaignMemory, BusinessProfile


def _make_campaign(
    cid: str = "genome-001",
    icp: str = "B2B SaaS founders",
    service: str = "Marketing SaaS",
    geography: str = "US",
    industry: str = "marketing agency",
) -> Campaign:
    biz = BusinessProfile(
        name="Test Co", service=service, icp=icp,
        geography=geography, goal="grow", industry=industry,
    )
    mem = CampaignMemory(
        business=biz,
        email_sequence="Outreach ready",
        content_strategy="Blog weekly",
        social_calendar="Mon: post",
        gtm_strategy="PLG",
    )
    return Campaign(id=cid, user_id="u1", memory=mem)


# ── record_campaign_dna ──────────────────────────────────────────────────────

class TestRecordDNA:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.genome = CampaignGenome()
        self.campaign = _make_campaign()

    async def test_creates_dna_entry(self):
        dna = await self.genome.record_campaign_dna(self.campaign)
        assert isinstance(dna, CampaignDNA)
        assert dna.campaign_id == "genome-001"
        assert dna.icp_type == "B2B SaaS founders"
        assert "genome-001" in self.genome._dna_store

    async def test_channel_mix_populated(self):
        dna = await self.genome.record_campaign_dna(self.campaign)
        assert dna.channel_mix["outreach"] is True
        assert dna.channel_mix["content"] is True
        assert dna.channel_mix["social"] is True

    async def test_outcomes_from_metrics(self):
        metrics = {"reply_rate": 5.0, "open_rate": 40.0, "cpa": 120.0}
        dna = await self.genome.record_campaign_dna(self.campaign, metrics=metrics)
        assert dna.outcomes["reply_rate"] == 5.0
        assert dna.outcomes["cpa"] == 120.0


# ── similarity_score ─────────────────────────────────────────────────────────

class TestSimilarityScore:
    def test_exact_match_returns_one(self):
        dna = CampaignDNA(
            campaign_id="x", icp_type="B2B SaaS", service_type="Marketing",
            geography="US", industry="tech",
        )
        score = dna.similarity_score(
            icp_type="B2B SaaS", service_type="Marketing",
            geography="US", industry="tech",
        )
        assert score == 1.0

    def test_no_criteria_returns_zero(self):
        dna = CampaignDNA(campaign_id="x", icp_type="B2B")
        score = dna.similarity_score()
        assert score == 0.0

    def test_partial_match(self):
        dna = CampaignDNA(
            campaign_id="x", icp_type="B2B SaaS", service_type="Marketing",
            geography="US", industry="tech",
        )
        score = dna.similarity_score(icp_type="B2B SaaS", geography="EU")
        # icp matches (1.0), geography doesn't (0.0) → 0.5
        assert 0.0 <= score <= 1.0
        assert score == 0.5

    def test_word_overlap_gives_partial_credit(self):
        dna = CampaignDNA(campaign_id="x", icp_type="enterprise SaaS CTOs")
        score = dna.similarity_score(icp_type="SaaS")
        # "SaaS" is a word in "enterprise SaaS CTOs" → partial 0.5
        assert 0.0 < score <= 1.0

    def test_score_always_in_range(self):
        dna = CampaignDNA(
            campaign_id="x", icp_type="anything",
            service_type="anything", geography="anywhere", industry="any",
        )
        for icp in ["B2B", "enterprise", "SMB", "anything"]:
            score = dna.similarity_score(icp_type=icp)
            assert 0.0 <= score <= 1.0


# ── query_intelligence ───────────────────────────────────────────────────────

class TestQueryIntelligence:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.genome = CampaignGenome()

    def test_empty_store_returns_zero_matches(self):
        result = self.genome.query_intelligence(icp_type="B2B")
        assert result["matches"] == 0

    async def test_with_multiple_campaigns(self):
        # Record three campaigns with different profiles
        c1 = _make_campaign("c1", icp="B2B SaaS", service="Marketing SaaS", industry="tech")
        c2 = _make_campaign("c2", icp="B2B SaaS", service="Sales SaaS", industry="tech")
        c3 = _make_campaign("c3", icp="D2C retail", service="E-commerce", industry="retail")

        await self.genome.record_campaign_dna(c1, metrics={"reply_rate": 5.0})
        await self.genome.record_campaign_dna(c2, metrics={"reply_rate": 3.0})
        await self.genome.record_campaign_dna(c3, metrics={"reply_rate": 8.0})

        result = self.genome.query_intelligence(icp_type="B2B SaaS", industry="tech")
        assert result["matches"] >= 2
        assert "avg_outcomes" in result
        assert "what_worked" in result
        assert "similar_campaigns" in result

    async def test_weighted_average_outcomes(self):
        c1 = _make_campaign("c1", icp="B2B SaaS", service="Marketing")
        c2 = _make_campaign("c2", icp="B2B SaaS", service="Marketing")
        await self.genome.record_campaign_dna(c1, metrics={"reply_rate": 4.0})
        await self.genome.record_campaign_dna(c2, metrics={"reply_rate": 6.0})

        result = self.genome.query_intelligence(icp_type="B2B SaaS")
        # Both should match; avg reply_rate should be between 4 and 6
        avg_rr = result["avg_outcomes"].get("reply_rate", 0)
        assert 3.0 <= avg_rr <= 7.0


# ── get_recommendations ──────────────────────────────────────────────────────

class TestGetRecommendations:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.genome = CampaignGenome()

    def test_no_data_returns_defaults(self):
        campaign = _make_campaign()
        recs = self.genome.get_recommendations(campaign)
        assert recs["has_data"] is False
        assert "default_channels" in recs
        assert isinstance(recs["default_channels"], list)

    async def test_with_data_returns_recommendations(self):
        # Seed the genome
        c1 = _make_campaign("c1", icp="B2B SaaS", service="Marketing SaaS", industry="marketing agency")
        await self.genome.record_campaign_dna(c1, metrics={"reply_rate": 5.0, "cpa": 100.0})

        # Query for a similar campaign
        campaign = _make_campaign("new", icp="B2B SaaS", service="Marketing SaaS", industry="marketing agency")
        recs = self.genome.get_recommendations(campaign)
        assert recs["has_data"] is True
        assert "recommendations" in recs
        assert isinstance(recs["recommendations"], list)
        assert "benchmarks" in recs
        assert "suggested_channels" in recs
