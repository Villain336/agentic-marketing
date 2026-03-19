"""
Hiring plans and worker classification checks.
"""

from __future__ import annotations

import json


async def _create_hiring_plan(service: str = "", current_revenue: str = "0", entity_type: str = "llc") -> str:
    """Generate revenue-triggered hiring plan."""
    et = (entity_type or "llc").lower()
    plan = {
        "entity_type": et,
        "hiring_model": "1099 contractors" if et == "sole_prop" else "W-2 + 1099 mix",
        "phases": [
            {"revenue_trigger": "$0-5K/mo", "hires": ["No hires — founder does everything"],
             "note": "Focus on sales and delivery. Automate what you can."},
            {"revenue_trigger": "$5K-15K/mo", "hires": ["1099 Contractor: Delivery Specialist", "1099 Contractor: VA (admin)"],
             "note": "Delegate delivery first so founder can sell."},
            {"revenue_trigger": "$15K-30K/mo", "hires": ["1099/W-2: Operations Manager", "1099: Content/Marketing"],
             "note": "Ops manager is the first critical hire. Frees founder for strategy."},
            {"revenue_trigger": "$30K-50K/mo", "hires": ["W-2: Account Manager", "1099: Sales Development"],
             "note": "Account management prevents churn. SDR drives growth."},
            {"revenue_trigger": "$50K+/mo", "hires": ["W-2: Department Leads", "W-2: Finance/Bookkeeper"],
             "note": "Build middle management. Founder becomes CEO."},
        ],
    }
    if et in ("s_corp", "c_corp"):
        plan["note"] = f"Owner is already W-2 employee of the {et.replace('_', '-').upper()}. Payroll is running from day 1."
    return json.dumps(plan)



async def _worker_classification_check(worker_role: str = "", state: str = "", hours_per_week: str = "0") -> str:
    """Check 1099 vs W-2 classification risk."""
    risk_factors = []
    hours = int(hours_per_week) if hours_per_week.isdigit() else 0
    if hours >= 30:
        risk_factors.append("Working 30+ hours/week — high risk of misclassification as employee")
    factors = {
        "behavioral_control": "Does the business control HOW the worker performs? If yes → employee indicator.",
        "financial_control": "Does the worker have unreimbursed expenses, opportunity for profit/loss? If yes → contractor indicator.",
        "relationship_type": "Is there a written contract? Benefits? Permanence? These all matter.",
    }
    return json.dumps({
        "worker_role": worker_role, "state": state, "hours_per_week": hours,
        "risk_factors": risk_factors, "irs_factors": factors,
        "recommendation": "Consult employment attorney if any risk factors present.",
        "state_note": f"{state} may have stricter rules than federal (e.g. CA ABC test, MA presumption of employment)" if state else "",
    })



def register_hr_tools(registry):
    """Register all hr tools with the given registry."""
    from models import ToolParameter

    registry.register("create_hiring_plan", "Generate revenue-triggered hiring plan adapted to entity type.",
        [ToolParameter(name="service", description="Service the business provides"),
         ToolParameter(name="current_revenue", description="Current monthly revenue", required=False),
         ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp", required=False)],
        _create_hiring_plan, "hr")

    registry.register("worker_classification_check", "Check 1099 vs W-2 classification risk for a worker role.",
        [ToolParameter(name="worker_role", description="Role/title of the worker"),
         ToolParameter(name="state", description="State of operation", required=False),
         ToolParameter(name="hours_per_week", description="Hours per week the worker does", required=False)],
        _worker_classification_check, "hr")

    # ── Sales Pipeline Tools ──

