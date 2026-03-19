"""
Omni OS Backend — White-Label API
Tenant isolation, custom branding, and reseller support.
Agencies can run the platform under their own brand.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger("supervisor.whitelabel")


class TenantConfig(BaseModel):
    """White-label tenant configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str                           # "Acme Marketing Agency"
    slug: str                           # "acme" — used in URLs
    owner_user_id: str = ""             # Supabase user ID of agency owner
    # Branding
    brand_name: str = ""                # Override platform name
    brand_logo_url: str = ""
    brand_color_primary: str = "#000000"
    brand_color_accent: str = "#0066FF"
    custom_domain: str = ""             # dashboard.acmeagency.com
    # Limits
    max_campaigns: int = 10
    max_agents_per_campaign: int = 27   # Default: all agents
    allowed_agent_ids: list[str] = []   # Empty = all agents allowed
    blocked_agent_ids: list[str] = []
    # Billing
    plan: str = "pro"                   # starter, pro, enterprise
    monthly_campaign_limit: int = 50
    monthly_agent_run_limit: int = 500
    # Feature flags
    features: dict[str, bool] = Field(default_factory=lambda: {
        "genome_intelligence": True,
        "ab_testing": True,
        "multi_campaign": True,
        "webhooks": True,
        "referral_engine": True,
        "wealth_architect": False,      # Premium add-on
        "portfolio_ops": True,
    })
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = True


class TenantManager:
    """Manages white-label tenants."""

    def __init__(self):
        self._tenants: dict[str, TenantConfig] = {}
        # user_id -> tenant_id mapping
        self._user_tenants: dict[str, str] = {}

    def create_tenant(self, name: str, slug: str, owner_user_id: str,
                      **kwargs) -> TenantConfig:
        """Create a new white-label tenant."""
        if any(t.slug == slug for t in self._tenants.values()):
            raise ValueError(f"Tenant slug '{slug}' already exists")

        tenant = TenantConfig(name=name, slug=slug,
                              owner_user_id=owner_user_id, **kwargs)
        self._tenants[tenant.id] = tenant
        self._user_tenants[owner_user_id] = tenant.id
        logger.info(f"Created tenant: {name} ({slug})")
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        return self._tenants.get(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Optional[TenantConfig]:
        for t in self._tenants.values():
            if t.slug == slug:
                return t
        return None

    def get_tenant_for_user(self, user_id: str) -> Optional[TenantConfig]:
        tid = self._user_tenants.get(user_id)
        return self._tenants.get(tid) if tid else None

    def add_user_to_tenant(self, user_id: str, tenant_id: str) -> bool:
        if tenant_id not in self._tenants:
            return False
        self._user_tenants[user_id] = tenant_id
        return True

    def is_agent_allowed(self, tenant: TenantConfig, agent_id: str) -> bool:
        """Check if an agent is allowed for this tenant."""
        if agent_id in tenant.blocked_agent_ids:
            return False
        if tenant.allowed_agent_ids and agent_id not in tenant.allowed_agent_ids:
            return False
        return True

    def is_feature_enabled(self, tenant: TenantConfig, feature: str) -> bool:
        """Check if a feature is enabled for this tenant."""
        return tenant.features.get(feature, False)

    def check_limits(self, tenant: TenantConfig, campaign_count: int,
                     monthly_runs: int) -> dict[str, Any]:
        """Check if tenant is within their plan limits."""
        return {
            "campaigns_used": campaign_count,
            "campaigns_limit": tenant.max_campaigns,
            "campaigns_ok": campaign_count < tenant.max_campaigns,
            "runs_used": monthly_runs,
            "runs_limit": tenant.monthly_agent_run_limit,
            "runs_ok": monthly_runs < tenant.monthly_agent_run_limit,
        }

    def update_tenant(self, tenant_id: str, **updates) -> Optional[TenantConfig]:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
        for key, val in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, val)
        return tenant

    def list_tenants(self) -> list[dict]:
        return [{
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "plan": t.plan,
            "active": t.active,
            "max_campaigns": t.max_campaigns,
            "created_at": t.created_at.isoformat(),
        } for t in self._tenants.values()]


# Singleton
tenant_manager = TenantManager()
