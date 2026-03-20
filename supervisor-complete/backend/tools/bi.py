"""
Business intelligence: metrics hierarchy, attribution, dashboards, ETL, and alerts.
"""

from __future__ import annotations

import json


async def _build_metrics_hierarchy(service: str = "", business_model: str = "retainer") -> str:
    """Build North Star → L1 → L2 → Leading indicators hierarchy."""
    return json.dumps({
        "north_star": "Monthly Recurring Revenue (MRR)" if business_model == "retainer" else "Monthly Revenue",
        "l1_metrics": [
            {"metric": "New Clients/Month", "target": "3-5", "source": "CRM"},
            {"metric": "Client Retention Rate", "target": ">90%", "source": "CRM"},
            {"metric": "Average Revenue Per Client", "target": "Varies", "source": "Billing"},
            {"metric": "Gross Margin", "target": ">60%", "source": "Accounting"},
        ],
        "l2_metrics": [
            {"metric": "Lead-to-Client Conversion Rate", "target": "15-25%", "source": "CRM"},
            {"metric": "Sales Cycle Length (days)", "target": "<30", "source": "CRM"},
            {"metric": "Customer Acquisition Cost", "target": "<1 month revenue", "source": "Marketing + Sales"},
            {"metric": "Lifetime Value", "target": ">3x CAC", "source": "Billing + CRM"},
            {"metric": "Net Promoter Score", "target": ">50", "source": "Survey"},
        ],
        "leading_indicators": [
            {"metric": "Qualified Leads/Week", "source": "Marketing"},
            {"metric": "Discovery Calls/Week", "source": "Calendar"},
            {"metric": "Proposals Sent/Week", "source": "CRM"},
            {"metric": "Website Traffic", "source": "Analytics"},
            {"metric": "Email Open Rate", "source": "ESP"},
            {"metric": "Social Engagement Rate", "source": "Social tools"},
            {"metric": "Content Published/Week", "source": "CMS"},
        ],
    })



async def _build_attribution_model(channels: str = "") -> str:
    """Design multi-touch attribution model."""
    return json.dumps({
        "recommended_model": "Position-Based (U-shaped)",
        "allocation": {
            "first_touch": "40% — credits the channel that brought them in",
            "middle_touches": "20% — split across all nurturing touchpoints",
            "last_touch": "40% — credits the channel that closed the deal",
        },
        "tracking_requirements": [
            "UTM parameters on all links (utm_source, utm_medium, utm_campaign)",
            "CRM integration to map touchpoints to deals",
            "Call tracking with dynamic number insertion",
            "Form tracking with hidden fields for attribution",
            "Cookie consent + first-party cookies for cross-session tracking",
        ],
        "channel_mapping": {
            "organic_search": "utm_source=google&utm_medium=organic",
            "paid_search": "utm_source=google&utm_medium=cpc",
            "social_organic": "utm_source=[platform]&utm_medium=social",
            "social_paid": "utm_source=[platform]&utm_medium=paid_social",
            "email": "utm_source=email&utm_medium=email&utm_campaign=[name]",
            "referral": "utm_source=referral&utm_medium=partner",
            "direct": "No UTM — direct traffic or dark social",
        },
    })



async def _build_dashboard_spec(business_name: str = "", metrics: str = "") -> str:
    """Generate executive dashboard specification."""
    return json.dumps({
        "dashboard_name": f"{business_name} Executive Dashboard",
        "refresh_cadence": "Real-time for revenue/leads, daily for everything else",
        "sections": [
            {"name": "Revenue", "kpis": ["MRR", "MRR Growth %", "Revenue vs Target", "Cash Collected"], "visualization": "Line chart + big numbers"},
            {"name": "Pipeline", "kpis": ["Open Deals ($)", "Deals by Stage", "Win Rate (30d)", "Avg Deal Size"], "visualization": "Funnel + bar chart"},
            {"name": "Marketing", "kpis": ["Leads This Week", "CAC", "Traffic", "Conversion Rate"], "visualization": "Sparklines + trend arrows"},
            {"name": "Delivery", "kpis": ["Active Clients", "Utilization %", "NPS Score", "Overdue Tasks"], "visualization": "Gauge + number"},
            {"name": "Finance", "kpis": ["Gross Margin", "Burn Rate", "Runway (months)", "AR Aging"], "visualization": "Big numbers + bar chart"},
        ],
        "recommended_tools": [
            {"tool": "Databox", "use": "Dashboard aggregation from multiple sources", "cost": "$0-72/mo"},
            {"tool": "Google Looker Studio", "use": "Free BI for GA4/GSC/Sheets data", "cost": "Free"},
            {"tool": "Notion", "use": "Internal scorecards and weekly reviews", "cost": "$8-10/mo"},
        ],
    })



async def _build_executive_dashboard(business_name: str, metrics: str = "", tools: str = "") -> str:
    """Build executive dashboard specification for human consumption."""
    return json.dumps({
        "dashboard_name": f"{business_name} — Executive Command Center",
        "sections": {
            "revenue_health": {
                "widgets": ["MRR trend (line)", "ARR gauge", "Collection rate (%)", "Pipeline value (bar)", "Revenue by source (pie)"],
                "update": "Real-time",
                "traffic_light": "Green > $10K MRR | Yellow $5-10K | Red < $5K",
            },
            "marketing_performance": {
                "widgets": ["Lead sources (funnel)", "CAC by channel (bar)", "Content engagement (sparklines)", "Social reach (counter)", "Email metrics (table)"],
                "update": "Daily",
            },
            "operations": {
                "widgets": ["Active clients (count)", "CSAT score (gauge)", "SLA compliance (%)", "Ticket backlog (bar)", "Delivery utilization (%)"],
                "update": "Hourly",
            },
            "financial": {
                "widgets": ["Cash flow (waterfall)", "Burn rate (trend)", "Runway (months)", "Tax reserves (gauge)", "P&L summary (table)"],
                "update": "Daily",
            },
            "agent_performance": {
                "widgets": ["Agent grades (heatmap)", "Scoring trends (sparklines)", "Active campaigns (cards)", "Genome insights (feed)"],
                "update": "After each agent run",
            },
        },
        "layout": "5-section grid, mobile-responsive, dark/light mode",
        "tools_recommended": ["Grafana + Supabase", "Retool", "Metabase", "Custom Next.js dashboard"],
    })



async def _build_agent_data_layer(agents: str = "") -> str:
    """Design structured data layer that agents can query for awareness."""
    return json.dumps({
        "data_layer_spec": {
            "endpoint": "/api/v1/agent-data/{agent_id}",
            "format": "JSON",
            "refresh": "After each agent run + scheduled intervals",
            "schema": {
                "campaign_health": {"type": "object", "fields": ["score", "grade", "trend", "risk_level"]},
                "revenue_metrics": {"type": "object", "fields": ["mrr", "arr", "collection_rate", "pipeline_value", "dso"]},
                "marketing_metrics": {"type": "object", "fields": ["leads", "cac", "ltv", "conversion_rates", "channel_performance"]},
                "operations_metrics": {"type": "object", "fields": ["csat", "sla_compliance", "utilization", "active_clients"]},
                "competitor_intel": {"type": "object", "fields": ["competitor_moves", "market_shifts", "pricing_changes"]},
                "economic_context": {"type": "object", "fields": ["macro_summary", "industry_trends", "risk_alerts"]},
                "governance_status": {"type": "object", "fields": ["compliance_rate", "upcoming_deadlines", "policy_updates"]},
            },
            "access_control": "Each agent sees data relevant to its function + global health metrics",
        },
        "benefits": [
            "Every agent makes decisions with full business context",
            "No agent operates in a silo — data flows bidirectionally",
            "Humans and agents see the same source of truth",
        ],
    })



async def _create_etl_pipeline(source: str, destination: str, transform: str = "", schedule: str = "hourly") -> str:
    """Design ETL pipeline specification."""
    return json.dumps({
        "pipeline": {
            "source": source,
            "destination": destination,
            "transform": transform or "Clean, deduplicate, normalize, validate schema",
            "schedule": schedule,
            "monitoring": {"freshness_check": True, "row_count_alert": True, "schema_drift_detection": True},
        },
        "recommended_tools": ["Airbyte (open-source)", "Fivetran", "dbt for transforms", "Dagster/Prefect for orchestration"],
    })



async def _create_alert_rules(metric: str, threshold: str, channel: str = "email", severity: str = "warning") -> str:
    """Create threshold-based alert rules."""
    return json.dumps({
        "alert": {
            "metric": metric,
            "condition": f"When {metric} crosses {threshold}",
            "severity": severity,
            "notification_channel": channel,
            "cooldown": "15 minutes (prevent alert storms)",
            "auto_action": "None (notify only)" if severity == "warning" else "Trigger agent re-run",
        },
    })



def register_bi_tools(registry):
    """Register all bi tools with the given registry."""
    from models import ToolParameter

    registry.register("build_metrics_hierarchy", "Build North Star → L1 → L2 → Leading indicators hierarchy.",
        [ToolParameter(name="service", description="Service/business type"),
         ToolParameter(name="business_model", description="Model: retainer, project, hourly, productized", required=False)],
        _build_metrics_hierarchy, "bi")

    registry.register("build_attribution_model", "Design multi-touch attribution model with tracking requirements.",
        [ToolParameter(name="channels", description="Current marketing channels (comma-separated)", required=False)],
        _build_attribution_model, "bi")

    registry.register("build_dashboard_spec", "Generate executive dashboard specification with KPIs and tool recommendations.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="metrics", description="Key metrics to include (comma-separated)", required=False)],
        _build_dashboard_spec, "bi")

    # ── Tax Optimization Tools ──

    registry.register("build_executive_dashboard", "Build executive dashboard specification for human-readable business overview.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="metrics", description="Key metrics to include", required=False),
         ToolParameter(name="tools", description="Preferred BI tools", required=False)],
        _build_executive_dashboard, "bi")

    registry.register("build_agent_data_layer", "Design structured data layer accessible by all agents for context-aware decisions.",
        [ToolParameter(name="agents", description="Comma-separated agent IDs to configure", required=False)],
        _build_agent_data_layer, "bi")

    registry.register("create_etl_pipeline", "Design ETL pipeline for extracting, transforming, and loading data between systems.",
        [ToolParameter(name="source", description="Data source: stripe, crm, email, social, ads, analytics"),
         ToolParameter(name="destination", description="Destination: data_warehouse, dashboard, agent_data_layer"),
         ToolParameter(name="transform", description="Transformation rules", required=False),
         ToolParameter(name="schedule", description="Schedule: realtime, hourly, daily, weekly", required=False)],
        _create_etl_pipeline, "bi")

    registry.register("create_alert_rules", "Configure threshold-based monitoring alerts for key business metrics.",
        [ToolParameter(name="metric", description="Metric to monitor"),
         ToolParameter(name="threshold", description="Alert threshold value or condition"),
         ToolParameter(name="channel", description="Notification channel: email, slack, sms", required=False),
         ToolParameter(name="severity", description="Severity: info, warning, critical", required=False)],
        _create_alert_rules, "bi")

    # ── Governance & Compliance Tools ──

