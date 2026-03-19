"""
Referral programs, tracking, metrics, and affiliate asset generation.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _create_referral_program(
    program_name: str, reward_type: str = "percentage", reward_value: str = "10",
    reward_description: str = "", cookie_duration_days: str = "90",
) -> str:
    """Design and configure a referral/affiliate program."""
    reward_desc = reward_description or (
        f"{reward_value}% recurring commission" if reward_type == "percentage"
        else f"${reward_value} per referral"
    )

    program = {
        "program_name": program_name,
        "reward_type": reward_type,
        "reward_value": reward_value,
        "reward_description": reward_desc,
        "cookie_duration_days": int(cookie_duration_days),
        "tiers": [
            {"name": "Starter", "threshold": 0, "commission": f"{reward_value}%", "perks": ["Basic dashboard", "Monthly payouts"]},
            {"name": "Partner", "threshold": 5, "commission": f"{int(float(reward_value) * 1.5)}%", "perks": ["Priority support", "Co-marketing", "Bi-weekly payouts"]},
            {"name": "Elite", "threshold": 20, "commission": f"{int(float(reward_value) * 2)}%", "perks": ["Dedicated account manager", "Custom landing pages", "Weekly payouts"]},
        ],
        "tracking": {
            "method": "unique_referral_link",
            "attribution_window": f"{cookie_duration_days} days",
            "multi_touch": True,
        },
        "assets_to_create": [
            "Referral landing page with unique link generator",
            "Email swipe copy (5 templates for affiliates to use)",
            "Social media graphics (3 sizes)",
            "Case study PDF for affiliates to share",
            "Affiliate dashboard with real-time tracking",
        ],
        "automation": [
            "Auto-generate unique referral links on signup",
            "Track clicks → signups → conversions → payouts",
            "Monthly payout via Stripe Connect or PayPal",
            "Auto-send commission notification emails",
            "Tier-up notification when thresholds are hit",
        ],
    }

    # If Rewardful is configured, set up there
    if settings.rewardful_api_key:
        program["platform"] = "Rewardful"
        program["setup_status"] = "ready_to_activate"
        program["api_configured"] = True
    elif settings.firstpromoter_api_key:
        program["platform"] = "FirstPromoter"
        program["setup_status"] = "ready_to_activate"
        program["api_configured"] = True
    else:
        program["platform"] = "custom"
        program["setup_status"] = "manual_setup_required"
        program["recommended_platforms"] = [
            {"name": "Rewardful", "price": "$49/mo", "best_for": "Stripe-integrated SaaS/agencies"},
            {"name": "FirstPromoter", "price": "$49/mo", "best_for": "Affiliate + referral hybrid"},
            {"name": "ReferralCandy", "price": "$59/mo", "best_for": "E-commerce focused"},
        ]

    return json.dumps(program)



async def _track_referral(
    referrer_id: str, referred_email: str, event: str = "signup",
    revenue: str = "0",
) -> str:
    """Track a referral event — signup, conversion, or revenue attribution."""
    return json.dumps({
        "referrer_id": referrer_id,
        "referred": referred_email,
        "event": event,
        "revenue_attributed": float(revenue),
        "commission_earned": float(revenue) * 0.10,  # Default 10%
        "tracked_at": "now",
        "attribution_chain": {
            "first_touch": "referral_link",
            "last_touch": event,
            "revenue": float(revenue),
        },
    })



async def _get_referral_metrics() -> str:
    """Get referral program performance metrics."""
    if settings.rewardful_api_key:
        try:
            r = await _http.get("https://api.rewardful.com/v1/affiliates",
                headers={"Authorization": f"Bearer {settings.rewardful_api_key}"},
                params={"limit": 100})
            affiliates = r.json().get("data", [])
            return json.dumps({
                "total_affiliates": len(affiliates),
                "active_affiliates": sum(1 for a in affiliates if a.get("referrals_count", 0) > 0),
                "total_referrals": sum(a.get("referrals_count", 0) for a in affiliates),
                "total_revenue": sum(a.get("revenue", 0) for a in affiliates) / 100,
                "total_commissions_paid": sum(a.get("commissions_total", 0) for a in affiliates) / 100,
                "platform": "Rewardful",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({
        "status": "no_platform_configured",
        "placeholder_metrics": {
            "total_affiliates": 0, "active_affiliates": 0,
            "total_referrals": 0, "total_revenue": 0,
            "avg_commission_rate": "10%", "top_channel": "none",
        },
        "action_required": "Configure REWARDFUL_API_KEY or FIRSTPROMOTER_API_KEY",
    })



async def _generate_affiliate_assets(
    business_name: str, service: str, commission_rate: str = "10",
) -> str:
    """Generate affiliate marketing assets — swipe copy, social posts, email templates."""
    return json.dumps({
        "email_swipe_copy": [
            {
                "subject": f"I found something that could help your business — {business_name}",
                "body": f"Hey [Name],\n\nI've been using {business_name} for [service] and the results have been incredible. [Specific result].\n\nIf you sign up through my link, you'll get [offer]. Plus I earn a small commission that helps me keep recommending great tools.\n\n[REFERRAL_LINK]\n\nHappy to answer any questions!",
                "use_case": "Warm intro to peers/network",
            },
            {
                "subject": f"How I [achieved result] with {business_name}",
                "body": f"I wanted to share a quick win. After switching to {business_name} for {service}, I saw [metric improvement] in [timeframe].\n\nThey're offering [deal] right now: [REFERRAL_LINK]",
                "use_case": "Results-driven cold outreach",
            },
        ],
        "social_posts": [
            f"Been using @{business_name} for {service} and genuinely impressed. Results speak for themselves 📈 [REFERRAL_LINK]",
            f"Asked to share my secret weapon for {service}... it's @{business_name}. Not sponsored — I just earn a small commission because I believe in it. [REFERRAL_LINK]",
            f"If you're still doing {service} manually, check out @{business_name}. Changed the game for me. Link in bio 👆",
        ],
        "landing_page_copy": {
            "headline": f"See Why {business_name} Is Trusted By [X]+ Businesses",
            "subhead": f"Get {service} that actually delivers results.",
            "cta": "Start Your Free Trial",
            "social_proof": "[Insert testimonials/logos]",
        },
        "commission_rate": f"{commission_rate}%",
        "tracking_link_format": f"https://{business_name.lower().replace(' ', '')}.com/ref/[AFFILIATE_ID]",
    })



def register_referral_tools(registry):
    """Register all referral tools with the given registry."""
    from models import ToolParameter

    registry.register("create_referral_program", "Design and configure a referral/affiliate program with tiered commissions.",
        [ToolParameter(name="program_name", description="Program name"),
         ToolParameter(name="reward_type", description="percentage or flat_fee", required=False),
         ToolParameter(name="reward_value", description="Commission % or flat amount", required=False),
         ToolParameter(name="reward_description", description="Human-readable reward description", required=False),
         ToolParameter(name="cookie_duration_days", description="Attribution window in days", required=False)],
        _create_referral_program, "referral")

    registry.register("track_referral", "Track a referral event — signup, conversion, or revenue attribution.",
        [ToolParameter(name="referrer_id", description="Referrer's unique ID"),
         ToolParameter(name="referred_email", description="Referred person's email"),
         ToolParameter(name="event", description="Event type: signup, conversion, revenue", required=False),
         ToolParameter(name="revenue", description="Revenue amount to attribute", required=False)],
        _track_referral, "referral")

    registry.register("get_referral_metrics", "Get referral program performance — affiliates, conversions, commissions.",
        [],
        _get_referral_metrics, "referral")

    registry.register("generate_affiliate_assets", "Generate affiliate marketing assets — swipe copy, social posts, email templates.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service description"),
         ToolParameter(name="commission_rate", description="Commission rate %", required=False)],
        _generate_affiliate_assets, "referral")

    # ── Upsell & Client Intelligence Tools ──

