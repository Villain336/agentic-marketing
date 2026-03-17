"""
Supervisor Backend — Subscription Tier Definitions
Gates agent access, LLM model quality, and usage limits by plan.
"""
from __future__ import annotations
from models import Tier


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION PLANS
# ═══════════════════════════════════════════════════════════════════════════════

# Tier ordering for comparison (higher = more powerful)
TIER_RANK = {Tier.FAST: 0, Tier.STANDARD: 1, Tier.STRONG: 2}


def cap_tier(requested: Tier, plan_max: Tier) -> Tier:
    """Cap a requested LLM tier to the plan's maximum."""
    if TIER_RANK.get(requested, 0) > TIER_RANK.get(plan_max, 0):
        return plan_max
    return requested


# ── Starter: Core 10 agents, fast models, low volume ─────────────────────────
STARTER_AGENTS = [
    "vision_interview",     # Onboarding
    "prospector",           # Find leads
    "outreach",             # Email sequences
    "content",              # Blog / copy
    "social",               # Social media posts
    "sitelaunch",           # Landing page + deploy
    "legal",                # Basic legal docs
    "marketing_expert",     # GTM strategy
    "newsletter",           # Email newsletter
    "analytics_agent",      # Basic analytics
]

# ── Pro: 30 agents, standard models, moderate volume ─────────────────────────
PRO_AGENTS = STARTER_AGENTS + [
    "cs",                   # Client success
    "ads",                  # Paid ads
    "ppc",                  # PPC management
    "procurement",          # Tool stack
    "finance",              # Financial planning
    "hr",                   # HR playbook
    "sales",                # Sales playbook
    "delivery",             # Service delivery
    "billing",              # Stripe billing
    "referral",             # Referral program
    "tax_strategist",       # Tax strategy
    "pr_comms",             # PR & media
    "economist",            # Economic intelligence
    "product_manager",      # Product roadmap
    "partnerships",         # BD & partnerships
    "competitive_intel",    # Competitive research
    "data_engineer",        # BI dashboards
    "governance",           # Compliance
    "client_fulfillment",   # Client delivery
    "knowledge_engine",     # Knowledge base
]

# ── Enterprise: All 41 agents, best models, unlimited ────────────────────────
ENTERPRISE_AGENTS = "__all__"  # Sentinel: all agents allowed


PLANS = {
    "starter": {
        "price_monthly": 49,
        "max_campaigns": 3,
        "max_agent_runs_monthly": 100,
        "llm_tier_cap": Tier.FAST,
        "agents": STARTER_AGENTS,
        "features": {
            "genome_intelligence": False,
            "ab_testing": False,
            "white_label": False,
        },
    },
    "pro": {
        "price_monthly": 149,
        "max_campaigns": 10,
        "max_agent_runs_monthly": 500,
        "llm_tier_cap": Tier.STANDARD,
        "agents": PRO_AGENTS,
        "features": {
            "genome_intelligence": True,
            "ab_testing": True,
            "white_label": False,
        },
    },
    "enterprise": {
        "price_monthly": 499,
        "max_campaigns": -1,       # unlimited
        "max_agent_runs_monthly": -1,
        "llm_tier_cap": Tier.STRONG,
        "agents": ENTERPRISE_AGENTS,
        "features": {
            "genome_intelligence": True,
            "ab_testing": True,
            "white_label": True,
        },
    },
}


def is_agent_allowed(plan: str, agent_id: str) -> bool:
    """Check if an agent is available on the given plan."""
    plan_cfg = PLANS.get(plan)
    if not plan_cfg:
        return False
    agents = plan_cfg["agents"]
    if agents == "__all__":
        return True
    return agent_id in agents


def get_plan_limits(plan: str) -> dict:
    """Get limits for a plan (for display / enforcement)."""
    plan_cfg = PLANS.get(plan, PLANS["starter"])
    return {
        "plan": plan,
        "price_monthly": plan_cfg["price_monthly"],
        "max_campaigns": plan_cfg["max_campaigns"],
        "max_agent_runs_monthly": plan_cfg["max_agent_runs_monthly"],
        "llm_tier_cap": plan_cfg["llm_tier_cap"].value,
        "agent_count": len(plan_cfg["agents"]) if isinstance(plan_cfg["agents"], list) else "unlimited",
        "features": plan_cfg["features"],
    }
