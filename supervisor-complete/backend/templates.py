"""
Supervisor Backend — Campaign Templates
Pre-built campaign configurations for common business types.
Skip onboarding for experienced users — go straight to execution.
"""
from __future__ import annotations
from typing import Any


TEMPLATES: dict[str, dict[str, Any]] = {

    "agency_launch": {
        "name": "Agency Launch",
        "description": "Full-stack agency launch — from formation to first client in 30 days",
        "ideal_for": "Marketing agencies, consulting firms, creative studios",
        "agents": [
            "marketing_expert", "legal", "formation", "finance",
            "prospector", "outreach", "content", "social",
            "sitelaunch", "newsletter", "cs", "billing", "referral",
        ],
        "business_defaults": {
            "goal": "Launch agency and acquire first 3 clients within 30 days",
            "entity_type": "llc",
        },
        "agent_config_overrides": {
            "prospector": {"max_iterations": 25},
            "outreach": {"max_iterations": 15},
        },
        "success_metrics": {
            "prospects_generated": 25,
            "meetings_booked": 5,
            "clients_signed": 3,
            "mrr_target": 15000,
        },
        "estimated_duration": "2-4 hours agent runtime",
    },

    "saas_gtm": {
        "name": "SaaS Go-to-Market",
        "description": "Full GTM strategy for SaaS products — positioning, launch, growth loops",
        "ideal_for": "SaaS startups, B2B software, developer tools",
        "agents": [
            "marketing_expert", "content", "social", "ads", "ppc",
            "sitelaunch", "newsletter", "analytics_agent",
            "prospector", "outreach", "cs", "billing", "referral",
        ],
        "business_defaults": {
            "goal": "Launch SaaS product and reach $10K MRR within 90 days",
        },
        "agent_config_overrides": {
            "content": {"max_iterations": 15},
            "ads": {"max_iterations": 12},
            "analytics_agent": {"max_iterations": 12},
        },
        "success_metrics": {
            "signups": 500,
            "trial_to_paid": 0.10,
            "mrr_target": 10000,
            "cac_target": 200,
        },
        "estimated_duration": "3-5 hours agent runtime",
    },

    "ecommerce_growth": {
        "name": "E-Commerce Growth",
        "description": "Multi-channel e-commerce growth — ads, social, email, SEO",
        "ideal_for": "D2C brands, Shopify stores, product companies",
        "agents": [
            "marketing_expert", "content", "social", "ads", "ppc",
            "newsletter", "sitelaunch", "analytics_agent",
            "cs", "billing", "referral",
        ],
        "business_defaults": {
            "goal": "Grow e-commerce revenue by 50% in 90 days through multi-channel acquisition",
        },
        "agent_config_overrides": {
            "ads": {"max_iterations": 15},
            "ppc": {"max_iterations": 12},
            "social": {"max_iterations": 10},
        },
        "success_metrics": {
            "roas_target": 4.0,
            "cpa_target": 50,
            "email_list_growth": 2000,
            "revenue_growth_pct": 50,
        },
        "estimated_duration": "2-3 hours agent runtime",
    },

    "consulting_practice": {
        "name": "Consulting Practice",
        "description": "Build a high-ticket consulting practice — positioning, pipeline, operations",
        "ideal_for": "Management consultants, strategy firms, fractional executives",
        "agents": [
            "marketing_expert", "legal", "finance", "tax_strategist",
            "prospector", "outreach", "content", "social",
            "sitelaunch", "cs", "sales", "delivery",
            "billing", "hr",
        ],
        "business_defaults": {
            "goal": "Build consulting practice to $25K/mo in 90 days",
            "entity_type": "s_corp",
        },
        "agent_config_overrides": {
            "prospector": {"max_iterations": 20},
            "sales": {"max_iterations": 15},
            "delivery": {"max_iterations": 12},
        },
        "success_metrics": {
            "clients_target": 5,
            "avg_deal_size": 5000,
            "pipeline_value": 100000,
            "mrr_target": 25000,
        },
        "estimated_duration": "3-5 hours agent runtime",
    },

    "local_business": {
        "name": "Local Business Growth",
        "description": "Local SEO, Google Ads, social proof — dominate your market area",
        "ideal_for": "Restaurants, clinics, law firms, real estate, home services",
        "agents": [
            "marketing_expert", "content", "social", "ads",
            "sitelaunch", "cs", "billing", "legal",
        ],
        "business_defaults": {
            "goal": "Become the #1 local business in our category within 6 months",
        },
        "agent_config_overrides": {
            "content": {"max_iterations": 12},  # Focus on local SEO content
        },
        "success_metrics": {
            "google_map_ranking": "top 3",
            "review_count_target": 50,
            "calls_per_month": 100,
            "local_seo_keywords_ranked": 20,
        },
        "estimated_duration": "1-2 hours agent runtime",
    },

    "wealth_builder": {
        "name": "Wealth Builder",
        "description": "Entity optimization, tax strategy, and wealth architecture for high earners",
        "ideal_for": "Entrepreneurs earning $200K+, business owners, high-income professionals",
        "agents": [
            "legal", "tax_strategist", "wealth_architect", "finance",
            "formation", "advisor",
        ],
        "business_defaults": {
            "goal": "Optimize business structure for maximum tax efficiency and wealth accumulation",
            "entity_type": "s_corp",
        },
        "agent_config_overrides": {
            "tax_strategist": {"max_iterations": 20},
            "wealth_architect": {"max_iterations": 20},
        },
        "success_metrics": {
            "tax_savings_identified": 30000,
            "structures_deployed": 2,
            "asset_protection_pct": 90,
        },
        "estimated_duration": "2-3 hours agent runtime",
    },

    "full_autonomous": {
        "name": "Full Autonomous",
        "description": "Every agent runs — complete business infrastructure from zero to operational",
        "ideal_for": "New businesses wanting everything set up, agencies managing full-service clients",
        "agents": "all",
        "business_defaults": {
            "goal": "Build complete business infrastructure and acquire first clients",
        },
        "success_metrics": {
            "agents_completed": "all",
            "infrastructure_score": 80,
            "pipeline_generated": True,
        },
        "estimated_duration": "4-8 hours agent runtime",
    },
}


def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)


def list_templates() -> list[dict]:
    return [{
        "id": tid,
        "name": t["name"],
        "description": t["description"],
        "ideal_for": t["ideal_for"],
        "agent_count": len(t["agents"]) if isinstance(t["agents"], list) else "all",
        "estimated_duration": t.get("estimated_duration", ""),
    } for tid, t in TEMPLATES.items()]
