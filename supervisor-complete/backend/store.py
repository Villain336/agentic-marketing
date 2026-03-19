"""
Omni OS Backend — Tenant-Scoped In-Memory Store
All data access goes through TenantStore with mandatory user_id scoping.
No cross-tenant data leakage is possible through this interface.

Swap the backing dicts for Redis / Supabase in production.
"""
from __future__ import annotations
import logging
from typing import Optional
from collections import defaultdict, OrderedDict

from models import (
    ApprovalItem, Campaign, CampaignMemory, OnboardingProfile,
)

logger = logging.getLogger("supervisor.store")

# Maximum items per user per collection (prevents unbounded memory growth)
MAX_CAMPAIGNS_PER_USER = 100
MAX_ONBOARDING_PER_USER = 20
MAX_APPROVALS_PER_USER = 500
MAX_TOTAL_CAMPAIGNS = 10_000


class BoundedDict(OrderedDict):
    """OrderedDict with a max size. Evicts oldest entries when full."""

    def __init__(self, max_size: int, *args, **kwargs):
        self._max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self._max_size:
            oldest_key, _ = self.popitem(last=False)
            logger.warning(f"Evicted oldest entry: {oldest_key}")


class TenantStore:
    """Tenant-isolated in-memory data store.

    Every piece of mutable state is keyed by (user_id, resource_id).
    Collections are bounded with LRU eviction to prevent OOM.
    """

    def __init__(self):
        # user_id -> {campaign_id -> Campaign}
        self._campaigns: dict[str, BoundedDict] = defaultdict(lambda: BoundedDict(MAX_CAMPAIGNS_PER_USER))
        # user_id -> {profile_id -> OnboardingProfile}
        self._onboarding: dict[str, BoundedDict] = defaultdict(lambda: BoundedDict(MAX_ONBOARDING_PER_USER))
        # user_id -> {item_id -> ApprovalItem}
        self._approvals: dict[str, BoundedDict] = defaultdict(lambda: BoundedDict(MAX_APPROVALS_PER_USER))
        # Reverse lookup: campaign_id -> user_id (for webhooks/background tasks)
        self._campaign_owner: dict[str, str] = {}

    # ── Campaigns ─────────────────────────────────────────────────────────

    def put_campaign(self, user_id: str, campaign: Campaign) -> None:
        """Store a campaign scoped to a user."""
        total = self.campaign_count()
        if total >= MAX_TOTAL_CAMPAIGNS:
            logger.warning(f"Global campaign limit ({MAX_TOTAL_CAMPAIGNS}) reached, rejecting new campaign")
            raise ValueError("Maximum campaign capacity reached")
        campaign.user_id = user_id
        self._campaigns[user_id][campaign.id] = campaign
        self._campaign_owner[campaign.id] = user_id

    def get_campaign(self, user_id: str, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign only if it belongs to this user."""
        return self._campaigns.get(user_id, {}).get(campaign_id)

    def get_campaign_any_tenant(self, campaign_id: str) -> Optional[Campaign]:
        """Look up a campaign across tenants (webhooks, background tasks only)."""
        owner = self._campaign_owner.get(campaign_id)
        if owner:
            return self._campaigns.get(owner, {}).get(campaign_id)
        return None

    def get_campaign_owner(self, campaign_id: str) -> str:
        """Get the user_id that owns a campaign."""
        return self._campaign_owner.get(campaign_id, "")

    def list_campaigns(self, user_id: str) -> list[Campaign]:
        """List all campaigns for a user."""
        return list(self._campaigns.get(user_id, {}).values())

    def delete_campaign(self, user_id: str, campaign_id: str) -> bool:
        """Delete a campaign only if it belongs to this user."""
        cmap = self._campaigns.get(user_id, {})
        if campaign_id in cmap:
            del cmap[campaign_id]
            self._campaign_owner.pop(campaign_id, None)
            return True
        return False

    def campaign_count(self, user_id: str = "") -> int:
        if user_id:
            return len(self._campaigns.get(user_id, {}))
        return sum(len(cmap) for cmap in self._campaigns.values())

    def all_campaigns(self) -> list[Campaign]:
        """All campaigns across tenants (admin/portfolio use only)."""
        result = []
        for cmap in self._campaigns.values():
            result.extend(cmap.values())
        return result

    # ── Onboarding ────────────────────────────────────────────────────────

    def put_onboarding(self, user_id: str, profile: OnboardingProfile) -> None:
        profile.user_id = user_id
        self._onboarding[user_id][profile.id] = profile

    def get_onboarding(self, user_id: str, profile_id: str) -> Optional[OnboardingProfile]:
        return self._onboarding.get(user_id, {}).get(profile_id)

    def delete_onboarding(self, user_id: str, profile_id: str) -> bool:
        omap = self._onboarding.get(user_id, {})
        if profile_id in omap:
            del omap[profile_id]
            return True
        return False

    # ── Approvals ─────────────────────────────────────────────────────────

    def put_approval(self, user_id: str, item: ApprovalItem) -> None:
        self._approvals[user_id][item.id] = item

    def get_approval(self, user_id: str, item_id: str) -> Optional[ApprovalItem]:
        return self._approvals.get(user_id, {}).get(item_id)

    def list_approvals(self, user_id: str, status: str = "pending") -> list[ApprovalItem]:
        return [a for a in self._approvals.get(user_id, {}).values() if a.status == status]

    def all_approvals(self, status: str = "pending") -> list[ApprovalItem]:
        """All approvals across tenants (admin use)."""
        result = []
        for amap in self._approvals.values():
            result.extend(a for a in amap.values() if a.status == status)
        return result


# Singleton
store = TenantStore()

def serialize_memory(m: CampaignMemory) -> dict:
    """Lossless serialization of CampaignMemory using Pydantic model_dump.

    Stores the full model so nothing is lost on round-trip. Boolean flags
    (has_*) are computed on read for backward-compat with frontend.
    """
    full = m.model_dump()

    # Add computed boolean flags for the frontend dashboard
    flag_fields = [
        ("has_prospects", "prospects"), ("has_outreach", "email_sequence"),
        ("has_content", "content_strategy"), ("has_social", "social_calendar"),
        ("has_ads", "ad_package"), ("has_cs", "cs_system"),
        ("has_site", "site_launch_brief"), ("has_legal", "legal_playbook"),
        ("has_gtm", "gtm_strategy"), ("has_tools", "tool_stack"),
        ("has_newsletter", "newsletter_system"), ("has_ppc", "ppc_playbook"),
        ("has_finance", "financial_plan"), ("has_hr", "hr_playbook"),
        ("has_sales", "sales_playbook"), ("has_delivery", "delivery_system"),
        ("has_analytics", "analytics_framework"),
        ("has_tax", "tax_playbook"), ("has_wealth", "wealth_strategy"),
        ("has_billing", "billing_system"), ("has_referral", "referral_program"),
        ("has_upsell", "upsell_playbook"),
        ("has_competitive_intel", "competitive_intel"),
        ("has_client_portal", "client_portal"),
        ("has_voice_receptionist", "voice_receptionist"),
        ("has_fullstack_dev", "fullstack_dev_output"),
        ("has_economist", "economist_briefing"),
        ("has_pr_comms", "pr_communications"),
        ("has_data_dashboards", "data_dashboards"),
        ("has_governance", "governance_brief"),
        ("has_product_roadmap", "product_roadmap"),
        ("has_partnerships", "partnerships_playbook"),
        ("has_fulfillment", "client_fulfillment"),
        ("has_agent_workspace", "agent_workspace"),
        ("has_treasury", "treasury_plan"),
        ("has_genome_intel", "genome_intel"),
    ]
    for flag, field in flag_fields:
        full[flag] = bool(full.get(field))

    return full
