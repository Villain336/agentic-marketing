"""Tests for data models."""
from __future__ import annotations

import pytest

from models import (
    Campaign,
    CampaignMemory,
    BusinessProfile,
    PerformanceEvent,
)


def _biz(**kwargs) -> BusinessProfile:
    defaults = dict(
        name="Acme", service="SaaS", icp="B2B", geography="US", goal="grow",
    )
    defaults.update(kwargs)
    return BusinessProfile(**defaults)


# ── Campaign creation ────────────────────────────────────────────────────────

class TestCampaignCreation:
    def test_creates_with_id(self):
        mem = CampaignMemory(business=_biz())
        c = Campaign(memory=mem)
        assert c.id  # auto-generated UUID
        assert c.status == "active"

    def test_explicit_id(self):
        mem = CampaignMemory(business=_biz())
        c = Campaign(id="my-camp", memory=mem)
        assert c.id == "my-camp"

    def test_memory_accessible(self):
        biz = _biz(name="TestBiz")
        mem = CampaignMemory(business=biz, prospect_count=5)
        c = Campaign(memory=mem)
        assert c.memory.business.name == "TestBiz"
        assert c.memory.prospect_count == 5


# ── CampaignMemory.to_context_string ─────────────────────────────────────────

class TestToContextString:
    def test_includes_business_fields(self):
        biz = _biz(name="Acme Corp", service="SEO Tools", icp="Agencies", geography="UK")
        mem = CampaignMemory(business=biz)
        ctx = mem.to_context_string()
        assert "BUSINESS: Acme Corp" in ctx
        assert "SERVICE: SEO Tools" in ctx
        assert "ICP: Agencies" in ctx
        assert "GEOGRAPHY: UK" in ctx

    def test_includes_entity_info(self):
        biz = _biz(entity_type="s_corp", state_of_formation="Delaware", founder_title="CEO")
        mem = CampaignMemory(business=biz)
        ctx = mem.to_context_string()
        assert "S-CORP" in ctx.upper() or "S_CORP" in ctx.upper()
        assert "Delaware" in ctx
        assert "CEO" in ctx

    def test_includes_industry(self):
        biz = _biz(industry="fintech")
        mem = CampaignMemory(business=biz)
        ctx = mem.to_context_string()
        assert "INDUSTRY: fintech" in ctx

    def test_status_labels(self):
        biz = _biz()
        mem = CampaignMemory(
            business=biz,
            email_sequence="ready",
            content_strategy="ready",
        )
        ctx = mem.to_context_string()
        assert "OUTREACH: sequence ready" in ctx
        assert "CONTENT: strategy built" in ctx

    def test_genome_intel_injected(self):
        biz = _biz()
        mem = CampaignMemory(business=biz, genome_intel="Similar campaigns averaged 5% reply rate")
        ctx = mem.to_context_string()
        assert "CROSS-CAMPAIGN INTELLIGENCE" in ctx
        assert "5% reply rate" in ctx


# ── entity_rules ─────────────────────────────────────────────────────────────

class TestEntityRules:
    def test_empty_entity_type_returns_empty(self):
        biz = _biz(entity_type="")
        mem = CampaignMemory(business=biz)
        assert mem.entity_rules() == ""

    def test_sole_prop_rules(self):
        biz = _biz(entity_type="sole_prop", state_of_formation="Texas", founder_title="Owner")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "SOLE-PROP" in rules.upper() or "SOLE_PROP" in rules.upper()
        assert "personally liable" in rules.lower()
        assert "Schedule C" in rules

    def test_llc_rules(self):
        biz = _biz(entity_type="llc", state_of_formation="Delaware", founder_title="Managing Member")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "LLC" in rules.upper()
        assert "Operating Agreement" in rules
        assert "Delaware" in rules

    def test_s_corp_rules(self):
        biz = _biz(entity_type="s_corp", state_of_formation="Wyoming")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "1120-S" in rules
        assert "reasonable salary" in rules.lower()

    def test_c_corp_rules(self):
        biz = _biz(entity_type="c_corp", state_of_formation="Nevada")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "Double taxation" in rules or "double taxation" in rules.lower()
        assert "21%" in rules

    def test_partnership_rules(self):
        biz = _biz(entity_type="partnership", state_of_formation="New York")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "K-1" in rules
        assert "1065" in rules

    def test_unknown_entity_type(self):
        biz = _biz(entity_type="cooperative")
        mem = CampaignMemory(business=biz)
        rules = mem.entity_rules()
        assert "cooperative" in rules.lower()
        assert "best practices" in rules.lower()


# ── BusinessProfile defaults ─────────────────────────────────────────────────

class TestBusinessProfileDefaults:
    def test_defaults(self):
        biz = _biz()
        assert biz.brand_context == ""
        assert biz.entity_type == ""
        assert biz.state_of_formation == ""
        assert biz.founder_title == ""
        assert biz.industry == ""

    def test_required_fields(self):
        # name, service, icp, geography, goal are required
        with pytest.raises(Exception):
            BusinessProfile(name="x")  # missing required fields


# ── PerformanceEvent ─────────────────────────────────────────────────────────

class TestPerformanceEvent:
    def test_creation(self):
        pe = PerformanceEvent(
            campaign_id="c1", source="sendgrid",
            event_type="email", data={"event": "delivered"},
        )
        assert pe.campaign_id == "c1"
        assert pe.source == "sendgrid"
        assert pe.data["event"] == "delivered"
        assert pe.id  # auto-generated
