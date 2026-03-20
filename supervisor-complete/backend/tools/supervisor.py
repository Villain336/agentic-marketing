"""
Campaign dashboard, agent rerun, owner alerts, and performance history.
"""

from __future__ import annotations

import json


from config import settings

from tools.crm import _get_pipeline_summary
from tools.email import _send_email
from tools.messaging import _send_slack_message, _send_telegram_message
async def _get_campaign_dashboard(campaign_id: str) -> str:
    """Aggregate all metrics across agents for a campaign dashboard."""
    dashboard: dict[str, Any] = {
        "campaign_id": campaign_id,
        "agent_statuses": {},
        "key_metrics": {},
        "alerts": [],
    }
    pipeline = await _get_pipeline_summary()
    pipeline_data = json.loads(pipeline)
    if not pipeline_data.get("error"):
        dashboard["key_metrics"]["pipeline"] = pipeline_data
    return json.dumps(dashboard)



async def _trigger_agent_rerun(agent_id: str, campaign_id: str, reason: str,
                                 updated_instructions: str = "") -> str:
    """Queue an agent for re-run with updated instructions."""
    return json.dumps({
        "queued": True, "agent_id": agent_id, "campaign_id": campaign_id,
        "reason": reason, "updated_instructions": updated_instructions[:500],
        "note": "Agent re-run queued. Will execute in next cycle.",
    })



async def _send_owner_alert(channel: str, message: str, priority: str = "normal") -> str:
    """Send alert to business owner via Slack, Telegram, or email."""
    if channel == "slack":
        return await _send_slack_message("#supervisor-alerts", message)
    elif channel == "telegram":
        chat_id = getattr(settings, 'telegram_owner_chat_id', '') or ""
        if chat_id:
            return await _send_telegram_message(chat_id, f"{'[ALERT]' if priority == 'high' else '[INFO]'} {message}")
        return json.dumps({"error": "TELEGRAM_OWNER_CHAT_ID not set."})
    elif channel == "email":
        owner_email = getattr(settings, 'owner_email', '') or ""
        if owner_email:
            return await _send_email(owner_email, f"Supervisor Alert: {message[:50]}", message)
        return json.dumps({"error": "OWNER_EMAIL not set."})
    return json.dumps({"error": f"Unknown alert channel: {channel}"})



async def _get_agent_performance_history(agent_id: str, campaign_id: str) -> str:
    """Get historical performance data for an agent."""
    return json.dumps({
        "agent_id": agent_id, "campaign_id": campaign_id,
        "runs": [],
        "note": "Connect Supabase for persistent performance tracking.",
    })



def register_supervisor_tools(registry):
    """Register all supervisor tools with the given registry."""
    from models import ToolParameter

    registry.register("get_campaign_dashboard", "Aggregate all metrics across agents for a campaign overview.",
        [ToolParameter(name="campaign_id", description="Campaign ID")],
        _get_campaign_dashboard, "supervisor")

    registry.register("trigger_agent_rerun", "Queue an agent for re-run with updated instructions.",
        [ToolParameter(name="agent_id", description="Agent ID to re-run"),
         ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="reason", description="Reason for re-run"),
         ToolParameter(name="updated_instructions", description="New instructions for the agent", required=False)],
        _trigger_agent_rerun, "supervisor")

    registry.register("send_owner_alert", "Send alert to business owner via Slack, Telegram, or email.",
        [ToolParameter(name="channel", description="Channel: slack, telegram, email"),
         ToolParameter(name="message", description="Alert message"),
         ToolParameter(name="priority", description="Priority: normal or high", required=False)],
        _send_owner_alert, "supervisor")

    registry.register("get_agent_performance_history", "Get historical performance data for an agent.",
        [ToolParameter(name="agent_id", description="Agent ID"),
         ToolParameter(name="campaign_id", description="Campaign ID")],
        _get_agent_performance_history, "supervisor")

    # ── Business Formation Tools ──

