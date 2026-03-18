"""
Supervisor Backend — Autonomy & Approval Enforcement

Controls what agents can do autonomously vs. what requires human approval.
Integrates with the engine's tool execution to gate sensitive actions.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger("supervisor.autonomy")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMY LEVELS
# ═══════════════════════════════════════════════════════════════════════════════

class AutonomyLevel:
    """
    Three levels of agent autonomy:
    - autonomous: Agent acts freely, no approval needed
    - guided: Agent acts but sensitive actions need approval
    - human_override: All actions need approval (observe-only mode)
    """
    AUTONOMOUS = "autonomous"
    GUIDED = "guided"
    HUMAN_OVERRIDE = "human_override"


# ═══════════════════════════════════════════════════════════════════════════════
# SENSITIVE TOOLS — Tools that require approval in guided mode
# ═══════════════════════════════════════════════════════════════════════════════

# Tools that spend money
SPENDING_TOOLS = {
    "send_email", "schedule_email_sequence", "send_sms",
    "make_phone_call", "create_meta_ad_campaign", "create_google_ads_campaign",
    "create_linkedin_ad_campaign", "deploy_to_vercel", "deploy_to_cloudflare",
    "register_domain", "create_subscription", "create_invoice",
    "send_payment_reminder", "post_twitter", "post_linkedin",
    "post_instagram", "schedule_social_post", "publish_to_cms",
    "create_referral_program",
}

# Tools that send outbound communications
OUTBOUND_TOOLS = {
    "send_email", "schedule_email_sequence", "send_sms",
    "make_phone_call", "send_linkedin_message", "post_twitter",
    "post_linkedin", "post_instagram", "post_to_reddit",
    "post_to_hackernews", "schedule_social_post",
    "send_slack_message", "send_telegram_message",
    "pitch_journalist", "draft_press_release",
}

# Tools that publish content publicly
CONTENT_PUBLISH_TOOLS = {
    "publish_to_cms", "deploy_to_vercel", "deploy_to_cloudflare",
    "post_twitter", "post_linkedin", "post_instagram",
    "post_to_reddit", "post_to_hackernews", "schedule_social_post",
    "build_full_website",
}

# Tools that modify infrastructure
INFRASTRUCTURE_TOOLS = {
    "deploy_to_vercel", "deploy_to_cloudflare", "manage_dns",
    "register_domain", "eks_create_cluster", "eks_deploy_workspace",
    "s3_upload", "sagemaker_train", "sagemaker_deploy_endpoint",
    "allocate_gpu",
}

# Tools that access sensitive data
DATA_TOOLS = {
    "create_crm_contact", "update_deal_stage",
    "find_contacts", "enrich_person", "find_phone_number",
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SETTINGS — Per-agent configuration
# ═══════════════════════════════════════════════════════════════════════════════

class AgentAutonomySettings(BaseModel):
    """Per-agent autonomy overrides and preferences."""
    agent_id: str
    autonomy_level: str = ""           # override global; "" = use global
    enabled: bool = True               # can be disabled entirely
    max_iterations: int = 0            # 0 = use default
    spending_limit: float = 0          # per-run spending limit; 0 = use global
    allowed_tools: list[str] = []      # whitelist; empty = all tools
    blocked_tools: list[str] = []      # blacklist; takes priority
    auto_approve_tools: list[str] = [] # always approve these tools
    notes: str = ""                    # user notes about this agent


class AutonomySettings(BaseModel):
    """Full autonomy configuration for a campaign/user."""
    global_level: str = "guided"
    spending_approval_threshold: float = 100.0
    outbound_approval_required: bool = True
    content_approval_required: bool = True
    infrastructure_approval_required: bool = True
    escalation_channel: str = "email"
    per_agent: dict[str, AgentAutonomySettings] = {}

    def get_agent_level(self, agent_id: str) -> str:
        """Get effective autonomy level for an agent."""
        agent_cfg = self.per_agent.get(agent_id)
        if agent_cfg and agent_cfg.autonomy_level:
            return agent_cfg.autonomy_level
        return self.global_level

    def is_agent_enabled(self, agent_id: str) -> bool:
        agent_cfg = self.per_agent.get(agent_id)
        if agent_cfg:
            return agent_cfg.enabled
        return True

    def get_spending_limit(self, agent_id: str) -> float:
        agent_cfg = self.per_agent.get(agent_id)
        if agent_cfg and agent_cfg.spending_limit > 0:
            return agent_cfg.spending_limit
        return self.spending_approval_threshold


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL CHECK — Called before tool execution
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalDecision(BaseModel):
    """Result of an autonomy check."""
    approved: bool = True
    reason: str = ""
    requires_approval: bool = False
    approval_type: str = ""     # "spending", "outbound", "content", "infrastructure"
    tool_name: str = ""
    agent_id: str = ""


def check_tool_approval(
    tool_name: str,
    agent_id: str,
    settings: AutonomySettings,
    estimated_cost: float = 0,
) -> ApprovalDecision:
    """
    Check whether a tool call is approved given the current autonomy settings.
    Returns an ApprovalDecision indicating whether the tool can proceed.
    """
    level = settings.get_agent_level(agent_id)
    agent_cfg = settings.per_agent.get(agent_id)

    # Autonomous mode: everything passes
    if level == AutonomyLevel.AUTONOMOUS:
        return ApprovalDecision(approved=True, reason="autonomous mode")

    # Human override: nothing passes
    if level == AutonomyLevel.HUMAN_OVERRIDE:
        return ApprovalDecision(
            approved=False,
            requires_approval=True,
            reason="human override mode — all actions require approval",
            approval_type="human_override",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Guided mode: check specific rules
    # Check per-agent auto-approve list
    if agent_cfg and tool_name in agent_cfg.auto_approve_tools:
        return ApprovalDecision(approved=True, reason="auto-approved for this agent")

    # Check per-agent blocked tools
    if agent_cfg and tool_name in agent_cfg.blocked_tools:
        return ApprovalDecision(
            approved=False,
            requires_approval=False,  # blocked, not approval-gated
            reason=f"tool '{tool_name}' is blocked for agent '{agent_id}'",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Check per-agent whitelist
    if agent_cfg and agent_cfg.allowed_tools and tool_name not in agent_cfg.allowed_tools:
        return ApprovalDecision(
            approved=False,
            requires_approval=False,
            reason=f"tool '{tool_name}' not in allowed list for agent '{agent_id}'",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Spending check
    if tool_name in SPENDING_TOOLS and estimated_cost > 0:
        limit = settings.get_spending_limit(agent_id)
        if estimated_cost > limit:
            return ApprovalDecision(
                approved=False,
                requires_approval=True,
                reason=f"estimated cost ${estimated_cost:.2f} exceeds limit ${limit:.2f}",
                approval_type="spending",
                tool_name=tool_name,
                agent_id=agent_id,
            )

    # Outbound check
    if settings.outbound_approval_required and tool_name in OUTBOUND_TOOLS:
        return ApprovalDecision(
            approved=False,
            requires_approval=True,
            reason=f"outbound communication requires approval",
            approval_type="outbound",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Content publish check
    if settings.content_approval_required and tool_name in CONTENT_PUBLISH_TOOLS:
        return ApprovalDecision(
            approved=False,
            requires_approval=True,
            reason=f"content publishing requires approval",
            approval_type="content",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Infrastructure check
    if settings.infrastructure_approval_required and tool_name in INFRASTRUCTURE_TOOLS:
        return ApprovalDecision(
            approved=False,
            requires_approval=True,
            reason=f"infrastructure changes require approval",
            approval_type="infrastructure",
            tool_name=tool_name,
            agent_id=agent_id,
        )

    # Default: approved in guided mode for non-sensitive tools
    return ApprovalDecision(approved=True, reason="guided mode — non-sensitive tool")


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS STORE — In-memory with persistence hooks
# ═══════════════════════════════════════════════════════════════════════════════

class AutonomyStore:
    """Manages autonomy settings per campaign."""

    def __init__(self):
        self._settings: dict[str, AutonomySettings] = {}  # campaign_id -> settings
        self._global_settings = AutonomySettings()

    def get(self, campaign_id: str = "") -> AutonomySettings:
        if campaign_id and campaign_id in self._settings:
            return self._settings[campaign_id]
        return self._global_settings

    def set(self, campaign_id: str, settings: AutonomySettings):
        self._settings[campaign_id] = settings

    def set_global(self, settings: AutonomySettings):
        self._global_settings = settings

    def update_agent(self, campaign_id: str, agent_id: str,
                     updates: dict) -> AgentAutonomySettings:
        settings = self.get(campaign_id)
        if agent_id not in settings.per_agent:
            settings.per_agent[agent_id] = AgentAutonomySettings(agent_id=agent_id)
        agent_cfg = settings.per_agent[agent_id]
        for k, v in updates.items():
            if hasattr(agent_cfg, k):
                setattr(agent_cfg, k, v)
        if campaign_id:
            self._settings[campaign_id] = settings
        else:
            self._global_settings = settings
        return agent_cfg

    def get_all_agent_settings(self, campaign_id: str = "") -> dict[str, dict]:
        settings = self.get(campaign_id)
        return {
            aid: cfg.model_dump()
            for aid, cfg in settings.per_agent.items()
        }

    def to_dict(self, campaign_id: str = "") -> dict:
        return self.get(campaign_id).model_dump()

    def from_onboarding(self, campaign_id: str, autonomy_config: dict):
        """Import autonomy settings from onboarding AutonomyConfig."""
        settings = AutonomySettings(
            global_level=autonomy_config.get("global_level", "guided"),
            spending_approval_threshold=autonomy_config.get("spending_approval_threshold", 100.0),
            outbound_approval_required=autonomy_config.get("outbound_approval_required", True),
            content_approval_required=autonomy_config.get("content_approval_required", True),
            escalation_channel=autonomy_config.get("escalation_channel", "email"),
        )
        # Import per-agent overrides
        for agent_id, level in autonomy_config.get("per_agent_overrides", {}).items():
            settings.per_agent[agent_id] = AgentAutonomySettings(
                agent_id=agent_id,
                autonomy_level=level,
            )
        self._settings[campaign_id] = settings
        return settings


# Singleton
autonomy_store = AutonomyStore()
