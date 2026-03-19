"""
Expansion analysis, QBR templates, and client health scoring.
"""

from __future__ import annotations

import json


async def _analyze_expansion_opportunities(
    client_name: str, current_services: str, monthly_revenue: str = "0",
    engagement_months: str = "0", satisfaction_score: str = "0",
) -> str:
    """Analyze a client for upsell/cross-sell opportunities based on usage and satisfaction."""
    revenue = float(monthly_revenue)
    months = int(engagement_months)
    csat = float(satisfaction_score) if satisfaction_score != "0" else 4.0

    opportunities = []

    # Time-based triggers
    if months >= 3 and csat >= 4.0:
        opportunities.append({
            "type": "upsell",
            "trigger": "3+ months + high satisfaction",
            "offer": "Premium tier / expanded scope",
            "estimated_revenue_increase": f"${revenue * 0.5:.0f}/mo",
            "timing": "Now — they're in the sweet spot",
            "approach": "QBR meeting → show ROI → propose expanded engagement",
        })

    if months >= 6:
        opportunities.append({
            "type": "cross_sell",
            "trigger": "6+ months relationship depth",
            "offer": "Adjacent service offering",
            "estimated_revenue_increase": f"${revenue * 0.3:.0f}/mo",
            "timing": "Next QBR or after delivering strong results",
            "approach": "Identify gaps in their current stack → propose filling them",
        })

    if revenue >= 3000:
        opportunities.append({
            "type": "upsell",
            "trigger": "High-value client",
            "offer": "Annual contract with discount",
            "estimated_revenue_increase": f"${revenue * 10:.0f} (annual lock-in)",
            "timing": "Before contract renewal",
            "approach": "Offer 10-15% discount for annual commitment → improves cash flow + retention",
        })

    if csat >= 4.5:
        opportunities.append({
            "type": "referral",
            "trigger": "Extremely satisfied client",
            "offer": "Referral incentive program",
            "estimated_revenue_increase": "1-3 new clients",
            "timing": "After delivering a major win",
            "approach": "Ask for introduction to 2-3 peers → offer referral credit",
        })

    # Low-hanging fruit
    services = current_services.lower()
    cross_sell_map = {
        "seo": ["PPC management", "content marketing", "social media"],
        "social": ["paid social ads", "influencer partnerships", "content"],
        "email": ["SMS marketing", "marketing automation", "newsletter"],
        "ads": ["landing page optimization", "CRO", "retargeting"],
        "web": ["SEO", "content strategy", "analytics setup"],
        "content": ["SEO", "social distribution", "email newsletter"],
    }
    for service_key, cross_sells in cross_sell_map.items():
        if service_key in services:
            for cs in cross_sells:
                if cs.lower() not in services:
                    opportunities.append({
                        "type": "cross_sell",
                        "trigger": f"Natural extension of {service_key}",
                        "offer": cs,
                        "estimated_revenue_increase": f"${revenue * 0.2:.0f}/mo",
                        "timing": "When current service is performing well",
                        "approach": f"Show how {cs} amplifies their {service_key} results",
                    })
                    break  # One cross-sell per service

    return json.dumps({
        "client": client_name,
        "current_mrr": revenue,
        "tenure_months": months,
        "satisfaction": csat,
        "opportunities": opportunities[:5],  # Top 5
        "total_expansion_potential": f"${sum(revenue * 0.3 for _ in opportunities[:5]):.0f}/mo",
        "priority": "high" if csat >= 4.0 and months >= 3 else "medium" if months >= 1 else "nurture",
    })



async def _build_qbr_template(
    client_name: str, service: str, key_metrics: str = "",
) -> str:
    """Build a Quarterly Business Review template for client expansion conversations."""
    return json.dumps({
        "qbr_template": {
            "title": f"Quarterly Business Review — {client_name}",
            "sections": [
                {
                    "name": "Results Recap",
                    "content": "Review key metrics and wins from the past quarter",
                    "data_needed": ["KPI dashboard", "Goal vs actual", "Top wins"],
                },
                {
                    "name": "ROI Analysis",
                    "content": "Connect spend to revenue impact",
                    "data_needed": ["Total spend", "Revenue attributed", "Cost per acquisition"],
                },
                {
                    "name": "Competitive Landscape",
                    "content": "What competitors are doing, market shifts",
                    "data_needed": ["Competitor analysis", "Industry benchmarks"],
                },
                {
                    "name": "Roadmap & Recommendations",
                    "content": "Next quarter priorities and growth opportunities",
                    "data_needed": ["Proposed scope changes", "New initiatives", "Budget recommendations"],
                },
                {
                    "name": "Expansion Discussion",
                    "content": "Natural transition to upsell/cross-sell",
                    "talk_track": [
                        f"Based on our results with {service}, we see opportunity in...",
                        "We've noticed [gap] that's limiting your growth...",
                        "Clients similar to you are seeing [X] results by adding...",
                        "We'd love to propose a pilot program for [new service]...",
                    ],
                },
            ],
            "best_practices": [
                "Lead with their wins, not your pitch",
                "Use their language and metrics, not yours",
                "Plant the expansion seed in the Roadmap section",
                "End with a specific next step, not an open question",
            ],
        },
    })



async def _client_health_score(
    client_name: str, monthly_revenue: str = "0",
    last_interaction_days: str = "0", support_tickets: str = "0",
    satisfaction_score: str = "0", contract_months_remaining: str = "12",
) -> str:
    """Calculate client health score and churn risk."""
    revenue = float(monthly_revenue)
    last_interaction = int(last_interaction_days)
    tickets = int(support_tickets)
    csat = float(satisfaction_score) if satisfaction_score != "0" else 3.5
    contract_remaining = int(contract_months_remaining)

    # Scoring components (0-100 each)
    engagement_score = max(0, 100 - (last_interaction * 3))  # -3 pts per day since contact
    satisfaction_score_val = min(100, csat * 20)  # 5.0 = 100
    support_score = max(0, 100 - (tickets * 10))  # Each ticket costs 10 pts
    contract_score = min(100, contract_remaining * 8)  # 12+ months = high

    health = (engagement_score * 0.3 + satisfaction_score_val * 0.35 +
              support_score * 0.15 + contract_score * 0.2)

    churn_risk = "low" if health >= 70 else "medium" if health >= 40 else "high"
    actions = []
    if last_interaction >= 14:
        actions.append("Schedule check-in call — too long since last contact")
    if csat < 4.0:
        actions.append("Send satisfaction survey — identify specific issues")
    if tickets >= 3:
        actions.append("Escalate to account manager — support volume high")
    if contract_remaining <= 3:
        actions.append("Start renewal conversation — contract expiring soon")
    if health >= 70:
        actions.append("Explore expansion — client is healthy and engaged")

    return json.dumps({
        "client": client_name,
        "health_score": round(health, 1),
        "churn_risk": churn_risk,
        "components": {
            "engagement": round(engagement_score, 1),
            "satisfaction": round(satisfaction_score_val, 1),
            "support": round(support_score, 1),
            "contract": round(contract_score, 1),
        },
        "monthly_revenue_at_risk": revenue if churn_risk == "high" else 0,
        "recommended_actions": actions,
    })



def register_upsell_tools(registry):
    """Register all upsell tools with the given registry."""
    from models import ToolParameter

    registry.register("analyze_expansion_opportunities", "Analyze a client for upsell/cross-sell opportunities based on usage and satisfaction.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="current_services", description="Comma-separated services they use"),
         ToolParameter(name="monthly_revenue", description="Current MRR from this client", required=False),
         ToolParameter(name="engagement_months", description="Months they've been a client", required=False),
         ToolParameter(name="satisfaction_score", description="CSAT score 1-5", required=False)],
        _analyze_expansion_opportunities, "upsell")

    registry.register("build_qbr_template", "Build a Quarterly Business Review template for client expansion conversations.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="key_metrics", description="Key metrics to highlight", required=False)],
        _build_qbr_template, "upsell")

    registry.register("client_health_score", "Calculate client health score and churn risk with recommended actions.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="monthly_revenue", description="Monthly revenue from client", required=False),
         ToolParameter(name="last_interaction_days", description="Days since last interaction", required=False),
         ToolParameter(name="support_tickets", description="Open support tickets", required=False),
         ToolParameter(name="satisfaction_score", description="CSAT score 1-5", required=False),
         ToolParameter(name="contract_months_remaining", description="Months until contract renewal", required=False)],
        _client_health_score, "upsell")

    # ── Multi-Campaign Orchestration Tools ──

