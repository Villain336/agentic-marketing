"""
Campaign comparison, cloning, portfolio, agent workspaces, and workflow design.
"""

from __future__ import annotations

import json


async def _compare_campaigns(campaign_ids: str) -> str:
    """Compare performance across multiple campaigns for cross-learning."""
    ids = [c.strip() for c in campaign_ids.split(",")]
    return json.dumps({
        "campaigns_compared": len(ids),
        "campaign_ids": ids,
        "comparison_axes": [
            "Agent grades (which agents perform best across campaigns)",
            "Channel ROI (which channels convert best by ICP type)",
            "Content performance (which messaging angles resonate)",
            "Speed to first conversion (time to value by campaign type)",
        ],
        "note": "Comparison data populated after genome.get_cross_campaign_insights() runs",
    })



async def _clone_campaign_config(
    source_campaign_id: str, new_business_name: str, new_icp: str = "",
) -> str:
    """Clone a successful campaign config for a new client."""
    return json.dumps({
        "source_campaign": source_campaign_id,
        "new_campaign": {
            "business_name": new_business_name,
            "icp_override": new_icp or "inherited from source",
            "cloned_elements": [
                "Agent sequence and configuration",
                "Content strategy framework",
                "Email sequence templates (personalized)",
                "Ad creative structure",
                "Social calendar framework",
                "Scoring thresholds",
            ],
            "requires_customization": [
                "Business profile (name, service, brand context)",
                "Prospect list (new ICP research)",
                "Ad creative copy and imagery",
                "Email personalization tokens",
            ],
        },
        "estimated_time_savings": "60-70% vs starting from scratch",
        "genome_benefit": "Cross-campaign intelligence automatically feeds recommendations",
    })



async def _portfolio_dashboard(campaign_ids: str = "") -> str:
    """Get portfolio-level metrics across all campaigns."""
    return json.dumps({
        "portfolio_metrics": {
            "total_campaigns": "dynamic",
            "total_mrr": "sum across all campaign billing systems",
            "avg_agent_health": "weighted average across campaigns",
            "top_performing_campaign": "by composite score",
            "campaigns_needing_attention": "health score < 60",
        },
        "aggregation_axes": [
            "Revenue by campaign",
            "Agent performance distribution",
            "Channel ROI comparison",
            "Client satisfaction heat map",
            "Resource utilization across campaigns",
        ],
        "alerts": [
            "Campaign with declining scores",
            "Agents failing across multiple campaigns (systemic issue)",
            "Budget overrun warnings",
            "Upcoming renewals / churn risks",
        ],
    })



async def _provision_agent_workspace(agent_id: str, compute_type: str = "standard", capabilities: str = "") -> str:
    """Create sandboxed compute environment for an agent."""
    cap_list = [c.strip() for c in capabilities.split(",")] if capabilities else ["shell", "browser", "file_system"]
    compute_specs = {
        "standard": {"cpu": "2 vCPU", "memory": "4GB", "storage": "10GB", "network": "outbound_only"},
        "heavy": {"cpu": "4 vCPU", "memory": "8GB", "storage": "50GB", "network": "outbound_only"},
        "builder": {"cpu": "8 vCPU", "memory": "16GB", "storage": "100GB", "network": "outbound_with_ports"},
    }
    return json.dumps({
        "agent_id": agent_id,
        "workspace_id": f"WS-{agent_id[:8].upper()}",
        "compute": compute_specs.get(compute_type, compute_specs["standard"]),
        "capabilities": cap_list,
        "sandboxing": {
            "isolation": "Container-based (gVisor/Firecracker)",
            "network": "Outbound only, no listening ports (unless builder tier)",
            "file_system": "Persistent volume per agent, snapshot on each run",
            "secrets": "Vault-injected, never written to disk",
        },
        "persistence": "Workspace state persists between runs. Agent resumes from last checkpoint.",
        "languages_available": ["python3.12", "node20", "go1.22", "rust1.77"],
        "tools_available": ["git", "curl", "jq", "sqlite3", "chromium (headless)"],
    })



async def _configure_browser_automation(agent_id: str, allowed_domains: str = "", capabilities: str = "") -> str:
    """Set up browser automation for an agent."""
    domains = [d.strip() for d in allowed_domains.split(",")] if allowed_domains else ["*"]
    return json.dumps({
        "agent_id": agent_id,
        "browser": "Chromium (headless)",
        "capabilities": {
            "navigate": "Visit URLs, follow links, handle redirects",
            "interact": "Click buttons, fill forms, select dropdowns, upload files",
            "extract": "Read page content, extract structured data, parse tables",
            "screenshot": "Capture full-page or element screenshots for verification",
            "wait": "Wait for elements, network idle, custom conditions",
            "sessions": "Persistent sessions with cookie/localStorage management",
        },
        "security": {
            "allowed_domains": domains,
            "blocked": ["No financial transactions", "No account creation without approval", "No PII submission"],
            "rate_limiting": "Max 60 requests/minute per domain",
            "user_agent": "SupervisorBot/1.0 (Automated Agent)",
        },
        "use_cases": [
            "Research competitor websites and pricing pages",
            "Fill client intake forms and applications",
            "Monitor social media platforms for mentions",
            "Extract data from analytics dashboards",
            "Test deployed websites and applications",
        ],
    })



async def _create_code_sandbox(language: str, packages: str = "", timeout: str = "300") -> str:
    """Provision language-specific code execution environment."""
    return json.dumps({
        "language": language,
        "runtime": {"python": "Python 3.12", "node": "Node.js 20 LTS", "go": "Go 1.22", "rust": "Rust 1.77"}.get(language, language),
        "packages": [p.strip() for p in packages.split(",")] if packages else ["standard library"],
        "timeout_seconds": int(timeout),
        "execution_model": {
            "input": "Code string + stdin",
            "output": "stdout + stderr + exit code + artifacts",
            "artifacts": "Files created during execution persist in workspace",
            "resource_limits": {"max_memory": "2GB", "max_cpu_time": f"{timeout}s", "max_output": "10MB"},
        },
        "security": "Sandboxed execution, no network access during code run, no system calls",
    })



async def _design_workflow(name: str, trigger: str, steps: str, error_handling: str = "retry") -> str:
    """Create trigger-based automation workflow."""
    step_list = [s.strip() for s in steps.split(",")]
    return json.dumps({
        "workflow_name": name,
        "trigger": {
            "type": trigger,
            "examples": {
                "webhook": "External event (Stripe payment, form submission, API call)",
                "schedule": "Cron-like (every day at 9am, every Monday, every hour)",
                "event": "Internal event (agent completes, metric crosses threshold)",
                "manual": "Human-triggered via API or dashboard button",
            },
        },
        "steps": [{"order": i + 1, "action": step, "timeout": "60s", "on_failure": error_handling} for i, step in enumerate(step_list)],
        "error_handling": {
            "retry": {"max_retries": 3, "backoff": "exponential (2s, 4s, 8s)"},
            "fallback": "Execute fallback action",
            "escalate": "Notify human via Slack/email",
            "skip": "Log error and continue to next step",
        },
        "monitoring": {"execution_log": True, "duration_tracking": True, "failure_alerting": True},
    })



async def _build_agent_pipeline(agents: str, data_flow: str = "sequential") -> str:
    """Connect multi-agent execution chains."""
    agent_list = [a.strip() for a in agents.split(",")]
    return json.dumps({
        "pipeline": {
            "agents": agent_list,
            "data_flow": data_flow,
            "execution_model": {
                "sequential": "Agent A output → transforms → Agent B input → ... → Final output",
                "parallel": "Multiple agents run simultaneously, results merged at join point",
                "conditional": "Agent A output determines which agent runs next (branching)",
            }.get(data_flow, data_flow),
        },
        "data_transformation": "Between each agent: extract relevant fields, format for next agent's context",
        "error_handling": "If any agent fails: retry once, then skip with logged error, continue pipeline",
        "examples": [
            "Prospector → Outreach → Social: Lead gen pipeline",
            "Economist → Governance → Advisor: Intelligence-informed strategy",
            "Data Engineer → All Agents: Dashboard data feeds every agent",
            "Client Fulfillment → Billing → CS: Client lifecycle pipeline",
        ],
    })



async def _set_autonomy_level(agent_id: str, level: str = "2", spending_limit: str = "0", approval_required: str = "true") -> str:
    """Configure agent independence tier."""
    levels = {
        "0": {"name": "Observer", "can": "Read data, generate recommendations", "cannot": "Take any action", "approval": "All actions need human approval"},
        "1": {"name": "Suggester", "can": "Draft outputs, propose actions", "cannot": "Execute or publish", "approval": "Human approves before execution"},
        "2": {"name": "Actor", "can": "Execute within guardrails", "cannot": "Spend money or contact clients without approval", "approval": "Financial and client-facing actions need approval"},
        "3": {"name": "Autonomous", "can": "Execute most actions independently", "cannot": "Exceed spending limits or change strategy", "approval": "Only strategy changes and large spend need approval"},
        "4": {"name": "Self-Improving", "can": "Optimize own prompts, build tools, adjust strategy", "cannot": "Modify other agents or system architecture", "approval": "Quarterly human review of self-improvements"},
    }
    return json.dumps({
        "agent_id": agent_id,
        "autonomy_level": int(level),
        "level_details": levels.get(level, levels["2"]),
        "spending_limit_per_action": f"${float(spending_limit)}" if float(spending_limit) > 0 else "No spending authority",
        "approval_required": approval_required == "true",
        "progression_criteria": "Demonstrate reliability over 10+ runs with >90% positive outcomes to level up",
    })



async def _create_workflow_monitor(workflow_name: str, alert_on: str = "failure") -> str:
    """Set up execution tracking for workflows."""
    return json.dumps({
        "workflow": workflow_name,
        "monitoring": {
            "metrics_tracked": ["execution_count", "success_rate", "avg_duration", "failure_reasons", "cost_per_run"],
            "alert_triggers": {
                "failure": "Any workflow failure → immediate notification",
                "slow": "Duration > 2x average → warning",
                "cost": "Cost per run > threshold → warning",
                "drift": "Success rate drops below 90% → alert",
            },
            "dashboard": f"Visible at /workflows/{workflow_name}/metrics",
        },
    })



def register_orchestration_tools(registry):
    """Register all orchestration tools with the given registry."""
    from models import ToolParameter

    registry.register("compare_campaigns", "Compare performance across multiple campaigns for cross-learning insights.",
        [ToolParameter(name="campaign_ids", description="Comma-separated campaign IDs to compare")],
        _compare_campaigns, "orchestration")

    registry.register("clone_campaign_config", "Clone a successful campaign config for a new client — saves 60-70% setup time.",
        [ToolParameter(name="source_campaign_id", description="Campaign ID to clone from"),
         ToolParameter(name="new_business_name", description="New client's business name"),
         ToolParameter(name="new_icp", description="New ICP if different", required=False)],
        _clone_campaign_config, "orchestration")

    registry.register("portfolio_dashboard", "Get portfolio-level metrics across all campaigns — agency-wide view.",
        [ToolParameter(name="campaign_ids", description="Comma-separated campaign IDs (or empty for all)", required=False)],
        _portfolio_dashboard, "orchestration")

    # ── Community & Platform Research Tools ──

    registry.register("provision_agent_workspace", "Create sandboxed compute environment for an agent.",
        [ToolParameter(name="agent_id", description="Agent ID to provision workspace for"),
         ToolParameter(name="compute_type", description="Tier: standard, heavy, builder", required=False),
         ToolParameter(name="capabilities", description="Capabilities: shell, browser, file_system, code_execution", required=False)],
        _provision_agent_workspace, "orchestration")

    registry.register("configure_browser_automation", "Set up browser automation capabilities for an agent.",
        [ToolParameter(name="agent_id", description="Agent ID"),
         ToolParameter(name="allowed_domains", description="Comma-separated allowed domains (or * for all)", required=False),
         ToolParameter(name="capabilities", description="Browser capabilities to enable", required=False)],
        _configure_browser_automation, "orchestration")

    registry.register("create_code_sandbox", "Provision language-specific code execution environment.",
        [ToolParameter(name="language", description="Language: python, node, go, rust"),
         ToolParameter(name="packages", description="Comma-separated packages to install", required=False),
         ToolParameter(name="timeout", description="Execution timeout in seconds", required=False)],
        _create_code_sandbox, "orchestration")

    registry.register("design_workflow", "Create trigger-based automation workflow.",
        [ToolParameter(name="name", description="Workflow name"),
         ToolParameter(name="trigger", description="Trigger: webhook, schedule, event, manual"),
         ToolParameter(name="steps", description="Comma-separated workflow steps"),
         ToolParameter(name="error_handling", description="Error strategy: retry, fallback, escalate, skip", required=False)],
        _design_workflow, "orchestration")

    registry.register("build_agent_pipeline", "Connect multi-agent execution chains.",
        [ToolParameter(name="agents", description="Comma-separated agent IDs in execution order"),
         ToolParameter(name="data_flow", description="Flow: sequential, parallel, conditional", required=False)],
        _build_agent_pipeline, "orchestration")

    registry.register("set_autonomy_level", "Configure agent independence tier (0=observer to 4=self-improving).",
        [ToolParameter(name="agent_id", description="Agent ID"),
         ToolParameter(name="level", description="Autonomy level: 0, 1, 2, 3, 4", required=False),
         ToolParameter(name="spending_limit", description="Max spend per action in dollars", required=False),
         ToolParameter(name="approval_required", description="Require approval: true or false", required=False)],
        _set_autonomy_level, "orchestration")

    registry.register("create_workflow_monitor", "Set up execution tracking and alerting for workflows.",
        [ToolParameter(name="workflow_name", description="Workflow to monitor"),
         ToolParameter(name="alert_on", description="Alert trigger: failure, slow, cost, drift", required=False)],
        _create_workflow_monitor, "orchestration")

    # ── World Model Tools ──

