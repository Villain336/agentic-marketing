"""
Client intake, welcome sequences, deliverable pipelines, milestones, and LTV.
"""

from __future__ import annotations

import json


async def _build_delivery_sop(service: str = "", phase: str = "onboarding") -> str:
    """Generate standard operating procedure for a delivery phase."""
    return json.dumps({
        "service": service, "phase": phase,
        "sop": {
            "objective": f"Standard procedure for the {phase} phase of {service} delivery",
            "steps": [
                {"step": 1, "action": "Send welcome email with expectations doc", "owner": "Account Manager", "timing": "Within 2 hours of contract signing"},
                {"step": 2, "action": "Schedule kickoff call", "owner": "Account Manager", "timing": "Within 24 hours"},
                {"step": 3, "action": "Collect all required assets/access", "owner": "Operations", "timing": "Before kickoff call"},
                {"step": 4, "action": "Run kickoff call (agenda: goals, timeline, communication cadence)", "owner": "Project Lead", "timing": "Within 3 business days"},
                {"step": 5, "action": "Set up project in PM tool with milestones", "owner": "Operations", "timing": "Within 24 hours of kickoff"},
                {"step": 6, "action": "Send client the project timeline and communication plan", "owner": "Account Manager", "timing": "Same day as kickoff"},
            ],
            "quality_gates": ["Client assets received", "Kickoff call completed", "Project plan approved by client"],
            "escalation": "If any step is blocked for >24 hours, escalate to Operations Manager",
        },
    })



async def _capacity_planning(service: str = "", hours_per_client: str = "10", team_size: str = "1") -> str:
    """Calculate capacity and utilization targets."""
    hpc = int(hours_per_client) if hours_per_client.isdigit() else 10
    ts = int(team_size) if team_size.isdigit() else 1
    billable_hours = 32  # per person per week (80% utilization)
    max_clients = (billable_hours * ts) // hpc if hpc > 0 else 0
    return json.dumps({
        "hours_per_client_weekly": hpc,
        "team_size": ts,
        "billable_hours_per_person": billable_hours,
        "utilization_target": "80%",
        "max_concurrent_clients": max_clients,
        "recommended_max": int(max_clients * 0.85),  # leave buffer
        "warning_threshold": int(max_clients * 0.9),
        "actions_at_capacity": ["Raise prices", "Hire next team member", "Waitlist new clients", "Reduce scope per client"],
    })



async def _build_client_intake(service: str, questions: str = "") -> str:
    """Generate structured client intake questionnaire."""
    return json.dumps({
        "service": service,
        "intake_form": {
            "sections": {
                "business_overview": [
                    "Company name and website",
                    "Industry and target market",
                    "Current revenue and growth stage",
                    "Number of employees",
                ],
                "goals_and_objectives": [
                    "Primary goal for this engagement (specific and measurable)",
                    "What does success look like in 30/60/90 days?",
                    "What have you tried before? What worked/didn't?",
                    "Key constraints: budget, timeline, resources",
                ],
                "brand_assets": [
                    "Logo files (SVG, PNG)",
                    "Brand guidelines document",
                    "Existing website URL",
                    "Social media accounts",
                    "Analytics access (Google Analytics, ad accounts)",
                ],
                "competitive_landscape": [
                    "Top 3 competitors",
                    "What differentiates you from them?",
                    "Competitor content/campaigns you admire",
                ],
                "communication_preferences": [
                    "Preferred communication channel (email, Slack, phone)",
                    "Preferred meeting cadence (weekly, biweekly)",
                    "Key stakeholders and decision-makers",
                    "Timezone and availability",
                ],
            },
            "follow_up_automation": "Auto-send reminder at 24hr and 48hr if incomplete",
        },
    })



async def _build_welcome_sequence(business_name: str, service: str, client_name: str = "") -> str:
    """Generate automated client welcome/onboarding sequence."""
    return json.dumps({
        "business": business_name,
        "service": service,
        "sequence": [
            {"timing": "Instant", "channel": "email", "subject": f"Welcome to {business_name}!", "content": "Payment confirmed, access credentials, what happens next, intake form link"},
            {"timing": "+1 hour", "channel": "sms", "content": "Quick text with kickoff booking link and intake form reminder"},
            {"timing": "+24 hours", "channel": "email", "subject": "Your kickoff call is booked!", "content": "Kickoff prep: what to bring, agenda preview, expectations"},
            {"timing": "+48 hours", "channel": "email", "subject": "Before your kickoff: quick prep", "content": "Asset collection checklist, portal access tutorial, FAQ link"},
            {"timing": "+7 days", "channel": "email", "subject": "Week 1 complete — here's what we built", "content": "First deliverables preview, milestone dashboard, feedback request"},
        ],
        "portal_access": {"url": f"portal.{business_name.lower().replace(' ', '')}.com", "credentials": "Auto-generated, emailed separately"},
    })



async def _build_deliverable_pipeline(service: str, timeline_days: str = "30") -> str:
    """Define production workflow with quality gates."""
    days = int(timeline_days)
    return json.dumps({
        "service": service,
        "total_timeline": f"{days} days",
        "phases": {
            "phase_1_discovery": {"days": f"1-{days//6}", "deliverables": ["Strategy document", "Research findings", "Competitive analysis"], "quality_gate": "Client approval of strategic direction"},
            "phase_2_production": {"days": f"{days//6+1}-{days//2}", "deliverables": ["Core deliverables in draft", "Review-ready assets"], "quality_gate": "Internal QA checklist passed"},
            "phase_3_review": {"days": f"{days//2+1}-{days*3//4}", "deliverables": ["Client review round 1", "Revision round (max 2)"], "quality_gate": "Client sign-off on all deliverables"},
            "phase_4_launch": {"days": f"{days*3//4+1}-{days}", "deliverables": ["Final assets live", "Performance tracking active", "First results report"], "quality_gate": "Everything live and tracking"},
        },
        "approval_workflow": "Draft → Internal QA → Client Review → Revision (max 2 rounds) → Final Approval → Go Live",
        "communication": "Client updated at every phase transition + weekly progress email",
    })



async def _track_client_milestone(client_name: str, milestone: str, status: str = "complete", notes: str = "") -> str:
    """Log client delivery milestone."""
    return json.dumps({
        "client": client_name,
        "milestone": milestone,
        "status": status,
        "notes": notes,
        "next_action": "Send milestone notification to client" if status == "complete" else f"Continue work on {milestone}",
        "logged_at": "now",
    })



async def _calculate_client_ltv(monthly_revenue: str, retention_months: str = "12", expansion_rate: str = "0") -> str:
    """Project client lifetime value."""
    mrr = float(monthly_revenue)
    months = int(retention_months)
    expansion = float(expansion_rate) / 100
    base_ltv = mrr * months
    expansion_ltv = sum(mrr * (1 + expansion) ** m for m in range(months))
    return json.dumps({
        "monthly_revenue": mrr,
        "avg_retention_months": months,
        "expansion_rate": f"{expansion*100}%",
        "base_ltv": f"${base_ltv:,.0f}",
        "ltv_with_expansion": f"${expansion_ltv:,.0f}",
        "cac_target": f"${base_ltv/3:,.0f} (LTV/3 rule)",
        "payback_period_target": f"{months//4} months (retain 75%+ of LTV)",
    })



def register_delivery_tools(registry):
    """Register all delivery tools with the given registry."""
    from models import ToolParameter

    registry.register("build_delivery_sop", "Generate standard operating procedure for a delivery phase.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="phase", description="Phase: onboarding, execution, review, handoff", required=False)],
        _build_delivery_sop, "delivery")

    registry.register("capacity_planning", "Calculate capacity, utilization targets, and max concurrent clients.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="hours_per_client", description="Hours per client per week", required=False),
         ToolParameter(name="team_size", description="Number of team members", required=False)],
        _capacity_planning, "delivery")

    # ── Business Intelligence / Analytics Tools ──

    registry.register("build_client_intake", "Generate structured client intake questionnaire for onboarding.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="questions", description="Additional custom questions", required=False)],
        _build_client_intake, "delivery")

    registry.register("build_welcome_sequence", "Generate automated client welcome/onboarding email+SMS sequence.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="client_name", description="Client name for personalization", required=False)],
        _build_welcome_sequence, "delivery")

    registry.register("build_deliverable_pipeline", "Define production workflow with phases, quality gates, and approval flows.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="timeline_days", description="Total timeline in days", required=False)],
        _build_deliverable_pipeline, "delivery")

    registry.register("track_client_milestone", "Log client delivery milestone with status and notifications.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="milestone", description="Milestone name"),
         ToolParameter(name="status", description="Status: complete, in_progress, blocked", required=False),
         ToolParameter(name="notes", description="Notes or context", required=False)],
        _track_client_milestone, "delivery")

    registry.register("calculate_client_ltv", "Project client lifetime value with expansion revenue modeling.",
        [ToolParameter(name="monthly_revenue", description="Monthly revenue from client"),
         ToolParameter(name="retention_months", description="Average retention in months", required=False),
         ToolParameter(name="expansion_rate", description="Monthly expansion rate %", required=False)],
        _calculate_client_ltv, "delivery")

    # ── Knowledge Engine Tools ──

