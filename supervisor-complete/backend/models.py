"""
Supervisor Backend — Data Models
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    TOOL_CALLING = "tool_calling"
    OBSERVING = "observing"
    DONE = "done"
    ERROR = "error"
    PAUSED = "paused"


class StepType(str, Enum):
    THINK = "think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    OUTPUT = "output"
    ERROR = "error"
    STATUS = "status"


class Tier(str, Enum):
    STRONG = "strong"
    STANDARD = "standard"
    FAST = "fast"


# ── Tool Models ───────────────────────────────────────────────────────────────

class ToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: Optional[list[str]] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter] = []
    category: str = "general"

    def to_anthropic_schema(self) -> dict:
        properties = {}
        required = []
        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }

    def to_openai_schema(self) -> dict:
        properties = {}
        required = []
        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }

    def to_google_schema(self) -> dict:
        properties = {}
        required = []
        type_map = {"string": "STRING", "integer": "INTEGER", "number": "NUMBER",
                     "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT"}
        for p in self.parameters:
            prop = {"type": type_map.get(p.type, "STRING"), "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "OBJECT", "properties": properties, "required": required},
        }


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    input: dict[str, Any] = {}


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    output: str = ""
    error: Optional[str] = None
    success: bool = True


# ── Agent Loop Models ─────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    step_number: int
    type: StepType
    content: str = ""
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    provider_used: str = ""
    model_used: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    campaign_id: str
    status: AgentStatus = AgentStatus.IDLE
    steps: list[AgentStep] = []
    final_output: str = ""
    memory_extracted: dict[str, Any] = {}
    total_iterations: int = 0
    total_duration_ms: int = 0
    providers_used: list[str] = []
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ── Campaign Models ───────────────────────────────────────────────────────────

class BusinessProfile(BaseModel):
    name: str
    service: str
    icp: str
    geography: str
    goal: str
    brand_context: str = ""


class CampaignMemory(BaseModel):
    business: BusinessProfile
    prospects: str = ""
    prospect_count: int = 0
    email_sequence: str = ""
    content_strategy: str = ""
    social_calendar: str = ""
    ad_package: str = ""
    cs_system: str = ""
    cs_complete: bool = False
    site_launch_brief: str = ""
    campaign_complete: bool = False
    legal_playbook: str = ""
    gtm_strategy: str = ""
    tool_stack: str = ""
    newsletter_system: str = ""
    ppc_playbook: str = ""

    def to_context_string(self) -> str:
        parts = [
            f"AGENCY: {self.business.name}",
            f"SERVICE: {self.business.service}",
            f"ICP: {self.business.icp}",
            f"GEOGRAPHY: {self.business.geography}",
            f"GOAL: {self.business.goal}",
        ]
        if self.business.brand_context:
            parts.append(f"BRAND CONTEXT: {self.business.brand_context}")
        status_map = [
            (self.prospect_count, f"PROSPECTS FOUND: {self.prospect_count}"),
            (self.email_sequence, "OUTREACH: sequence ready"),
            (self.content_strategy, "CONTENT: strategy built"),
            (self.social_calendar, "SOCIAL: 7-day calendar ready"),
            (self.ad_package, "ADS: package ready"),
            (self.cs_system, "CLIENT SUCCESS: system ready"),
            (self.gtm_strategy, "GTM: strategy built"),
            (self.legal_playbook, "LEGAL: playbook ready"),
            (self.tool_stack, "PROCUREMENT: tool stack defined"),
            (self.newsletter_system, "NEWSLETTER: system ready"),
            (self.ppc_playbook, "PPC: optimization playbook ready"),
        ]
        for val, label in status_map:
            if val:
                parts.append(label)
        return "\n".join(parts)


class Campaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    memory: CampaignMemory
    agent_runs: dict[str, AgentRun] = {}
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── API Models ────────────────────────────────────────────────────────────────

class RunAgentRequest(BaseModel):
    agent_id: str
    campaign_id: Optional[str] = None
    business: BusinessProfile
    memory: dict[str, Any] = {}
    tier: Tier = Tier.STANDARD


class RunCampaignRequest(BaseModel):
    business: BusinessProfile
    start_from: Optional[str] = None
    tier: Tier = Tier.STANDARD
    brand_docs: list[str] = []


class AgentStreamEvent(BaseModel):
    event: StepType
    agent_id: str
    step: int = 0
    content: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    provider: str = ""
    model: str = ""
    status: AgentStatus = AgentStatus.EXECUTING
    memory_update: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    providers: list[dict] = []
    active_campaigns: int = 0
    version: str = "0.1.0"


# ── Onboarding Models ────────────────────────────────────────────────────────

class BusinessBrief(BaseModel):
    name: str = ""
    service_definition: str = ""
    value_proposition: str = ""
    icp_firmographic: str = ""
    icp_psychographic: str = ""
    competitive_positioning: str = ""
    founder_advantage: str = ""
    pricing_hypothesis: str = ""
    conversation_transcript: str = ""


class VisualDNA(BaseModel):
    color_palette: dict[str, Any] = {}
    typography: dict[str, Any] = {}
    photography_direction: str = ""
    illustration_style: str = ""
    layout_preferences: str = ""
    density: str = "balanced"
    brand_personality: str = ""
    anti_patterns: list[str] = []
    reference_urls: list[str] = []
    competitor_urls: list[str] = []


class FormationProfile(BaseModel):
    entity_type: str = ""
    state_of_formation: str = ""
    registered_agent: str = ""
    ein: str = ""
    bank_name: str = ""
    bank_account_status: str = "pending"
    insurance_types: list[str] = []
    insurance_status: str = ""
    legal_checklist: str = ""


class RevenueModel(BaseModel):
    pricing_model: str = ""
    price_point: str = ""
    target_clients_30d: int = 0
    target_clients_90d: int = 0
    target_revenue_90d: float = 0
    target_revenue_year1: float = 0
    startup_capital: float = 0
    budget_allocation: dict[str, float] = {}
    persona_pricing_feedback: str = ""


class AutonomyConfig(BaseModel):
    global_level: str = "guided"
    per_agent_overrides: dict[str, str] = {}
    spending_approval_threshold: float = 100.0
    outbound_approval_required: bool = True
    content_approval_required: bool = True
    escalation_channel: str = "email"


class OnboardingProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    business_brief: BusinessBrief = Field(default_factory=BusinessBrief)
    visual_dna: VisualDNA = Field(default_factory=VisualDNA)
    formation: FormationProfile = Field(default_factory=FormationProfile)
    revenue_model: RevenueModel = Field(default_factory=RevenueModel)
    channels: dict[str, Any] = {}
    market_research: dict[str, Any] = {}
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
    mood_board_references: list[str] = []
    mood_board_images: list[str] = []
    current_stage: int = 1
    completed_stages: list[int] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VisualAnalysis(BaseModel):
    dominant_colors: list[str] = []
    typography_classification: str = ""
    layout_pattern: str = ""
    photography_style: str = ""
    vibe_keywords: list[str] = []


# ── Brand System Models ──────────────────────────────────────────────────────

class BrandSystem(BaseModel):
    campaign_id: str = ""
    color_system: dict[str, Any] = {}
    typography_system: dict[str, Any] = {}
    spacing_system: dict[str, Any] = {}
    component_patterns: dict[str, Any] = {}
    photography_direction: str = ""
    anti_patterns: list[str] = []
    full_system: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Approval Queue Model ────────────────────────────────────────────────────

class ApprovalItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    agent_id: str = ""
    action_type: str = ""
    content: dict[str, Any] = {}
    status: str = "pending"
    decided_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None


# ── Spend & Revenue Models ───────────────────────────────────────────────────

class SpendEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    agent_id: str = ""
    amount: float = 0
    tool: str = ""
    description: str = ""
    approved_by: str = "auto"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RevenueEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    amount: float = 0
    client_id: str = ""
    source_agent: str = ""
    attribution_chain: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PerformanceEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    source: str = ""
    event_type: str = ""
    data: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
