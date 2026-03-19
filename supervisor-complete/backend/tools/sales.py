"""
Sales pipeline building and discovery call scripts.
"""

from __future__ import annotations

import json


async def _build_sales_pipeline(service: str = "", avg_deal_size: str = "0", sales_cycle_days: str = "30") -> str:
    """Build CRM pipeline stages with conversion targets."""
    return json.dumps({
        "pipeline_stages": [
            {"stage": "Lead", "description": "New inbound or outbound lead", "target_conversion": "40%", "actions": ["Qualify via BANT", "Add to CRM", "Schedule discovery"]},
            {"stage": "Discovery", "description": "Discovery call completed", "target_conversion": "60%", "actions": ["Run discovery script", "Identify pain/budget/timeline", "Send recap email"]},
            {"stage": "Proposal", "description": "Proposal sent", "target_conversion": "50%", "actions": ["Send custom proposal", "Include 3 pricing tiers", "Set follow-up reminder"]},
            {"stage": "Negotiation", "description": "Active negotiation", "target_conversion": "70%", "actions": ["Handle objections", "Offer concessions strategically", "Get verbal commit"]},
            {"stage": "Closed Won", "description": "Contract signed, payment received", "target_conversion": "100%", "actions": ["Send contract", "Collect payment", "Trigger onboarding"]},
            {"stage": "Closed Lost", "description": "Deal lost", "target_conversion": "—", "actions": ["Log reason", "Add to nurture sequence", "Review in retrospective"]},
        ],
        "velocity_targets": {
            "avg_deal_size": avg_deal_size,
            "sales_cycle_days": sales_cycle_days,
            "target_win_rate": "35-45% overall",
            "leads_needed_monthly": "Based on your targets, work backwards from revenue goal",
        },
    })



async def _generate_discovery_script(service: str = "", icp: str = "") -> str:
    """Generate discovery call script with objection handling."""
    return json.dumps({
        "opening": f"Thanks for taking the time. I'd love to understand your situation before I talk about what we do. Can you walk me through [specific pain related to {service}]?",
        "questions": {
            "pain": ["What's the biggest challenge you're facing with [area]?", "How long has this been a problem?", "What have you tried so far?"],
            "impact": ["What does this cost you monthly — in time, money, or missed opportunities?", "If you don't solve this in the next 6 months, what happens?"],
            "budget": ["Do you have a budget allocated for solving this?", "What would solving this be worth to you monthly?"],
            "authority": ["Who else is involved in this decision?", "What does your decision process look like?"],
            "timeline": ["When would you ideally want to start?", "Is there a deadline driving this?"],
        },
        "objection_handling": {
            "too_expensive": "I understand. Let me ask — what's the cost of NOT solving this? [Reframe value vs price]",
            "need_to_think": "Totally fair. What specifically do you need to think through? [Identify real objection]",
            "talking_to_others": "Smart to compare. What criteria are most important to you? [Position your differentiator]",
            "bad_timing": "When would be better? Let me send you something useful in the meantime. [Stay in touch]",
        },
        "close": "Based on what you've told me, here's what I'd recommend... [Prescribe, don't pitch]. Can I send you a proposal by [date]?",
    })



def register_sales_tools(registry):
    """Register all sales tools with the given registry."""
    from models import ToolParameter

    registry.register("build_sales_pipeline", "Build CRM pipeline stages with conversion targets and actions.",
        [ToolParameter(name="service", description="Service being sold"),
         ToolParameter(name="avg_deal_size", description="Average deal size in dollars", required=False),
         ToolParameter(name="sales_cycle_days", description="Average sales cycle length in days", required=False)],
        _build_sales_pipeline, "sales")

    registry.register("generate_discovery_script", "Generate discovery call script with objection handling library.",
        [ToolParameter(name="service", description="Service being sold"),
         ToolParameter(name="icp", description="Ideal customer profile", required=False)],
        _generate_discovery_script, "sales")

    # ── Delivery & Operations Tools ──

