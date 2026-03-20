"""Tests for tenant-scoped store — verifies data isolation between tenants."""
from __future__ import annotations
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from store import TenantStore
from models import Campaign, CampaignMemory, BusinessProfile, OnboardingProfile, ApprovalItem


@pytest.fixture
def ts():
    return TenantStore()


@pytest.fixture
def biz():
    return BusinessProfile(name="Acme", service="SaaS", icp="B2B", geography="US", goal="Grow")


def _make_campaign(biz, cid="c-1"):
    return Campaign(id=cid, memory=CampaignMemory(business=biz))


# ── Campaign isolation ────────────────────────────────────────────────────────

class TestCampaignIsolation:
    def test_put_and_get(self, ts, biz):
        c = _make_campaign(biz)
        ts.put_campaign("user-a", c)
        assert ts.get_campaign("user-a", c.id) is c

    def test_cross_tenant_invisible(self, ts, biz):
        c = _make_campaign(biz)
        ts.put_campaign("user-a", c)
        assert ts.get_campaign("user-b", c.id) is None

    def test_list_scoped(self, ts, biz):
        ts.put_campaign("user-a", _make_campaign(biz, "c-1"))
        ts.put_campaign("user-a", _make_campaign(biz, "c-2"))
        ts.put_campaign("user-b", _make_campaign(biz, "c-3"))
        assert len(ts.list_campaigns("user-a")) == 2
        assert len(ts.list_campaigns("user-b")) == 1
        assert len(ts.list_campaigns("user-x")) == 0

    def test_delete_only_own(self, ts, biz):
        c = _make_campaign(biz, "c-1")
        ts.put_campaign("user-a", c)
        assert ts.delete_campaign("user-b", "c-1") is False
        assert ts.delete_campaign("user-a", "c-1") is True
        assert ts.get_campaign("user-a", "c-1") is None

    def test_any_tenant_lookup(self, ts, biz):
        c = _make_campaign(biz, "c-1")
        ts.put_campaign("user-a", c)
        assert ts.get_campaign_any_tenant("c-1") is c
        assert ts.get_campaign_any_tenant("nonexistent") is None

    def test_owner_lookup(self, ts, biz):
        c = _make_campaign(biz, "c-1")
        ts.put_campaign("user-a", c)
        assert ts.get_campaign_owner("c-1") == "user-a"
        assert ts.get_campaign_owner("nonexistent") == ""

    def test_campaign_count(self, ts, biz):
        ts.put_campaign("user-a", _make_campaign(biz, "c-1"))
        ts.put_campaign("user-b", _make_campaign(biz, "c-2"))
        assert ts.campaign_count("user-a") == 1
        assert ts.campaign_count() == 2

    def test_user_id_set_on_campaign(self, ts, biz):
        c = _make_campaign(biz)
        ts.put_campaign("user-a", c)
        assert c.user_id == "user-a"

    def test_all_campaigns(self, ts, biz):
        ts.put_campaign("user-a", _make_campaign(biz, "c-1"))
        ts.put_campaign("user-b", _make_campaign(biz, "c-2"))
        assert len(ts.all_campaigns()) == 2


# ── Onboarding isolation ─────────────────────────────────────────────────────

class TestOnboardingIsolation:
    def test_put_and_get(self, ts):
        p = OnboardingProfile(id="p-1")
        ts.put_onboarding("user-a", p)
        assert ts.get_onboarding("user-a", "p-1") is p

    def test_cross_tenant_invisible(self, ts):
        p = OnboardingProfile(id="p-1")
        ts.put_onboarding("user-a", p)
        assert ts.get_onboarding("user-b", "p-1") is None

    def test_delete_only_own(self, ts):
        p = OnboardingProfile(id="p-1")
        ts.put_onboarding("user-a", p)
        assert ts.delete_onboarding("user-b", "p-1") is False
        assert ts.delete_onboarding("user-a", "p-1") is True


# ── Approval isolation ────────────────────────────────────────────────────────

class TestApprovalIsolation:
    def test_put_and_get(self, ts):
        item = ApprovalItem(id="a-1", status="pending")
        ts.put_approval("user-a", item)
        assert ts.get_approval("user-a", "a-1") is item

    def test_cross_tenant_invisible(self, ts):
        item = ApprovalItem(id="a-1", status="pending")
        ts.put_approval("user-a", item)
        assert ts.get_approval("user-b", "a-1") is None

    def test_list_filtered_by_status(self, ts):
        ts.put_approval("user-a", ApprovalItem(id="a-1", status="pending"))
        ts.put_approval("user-a", ApprovalItem(id="a-2", status="approved"))
        assert len(ts.list_approvals("user-a", "pending")) == 1
        assert len(ts.list_approvals("user-a", "approved")) == 1

    def test_all_approvals_across_tenants(self, ts):
        ts.put_approval("user-a", ApprovalItem(id="a-1", status="pending"))
        ts.put_approval("user-b", ApprovalItem(id="a-2", status="pending"))
        assert len(ts.all_approvals("pending")) == 2
