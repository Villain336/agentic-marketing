"""
Omni OS Backend — Data Models
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
    # Entity flow — set during onboarding, flows to every agent
    entity_type: str = ""          # sole_prop, llc, s_corp, c_corp, partnership
    state_of_formation: str = ""   # e.g. "Delaware", "Wyoming"
    founder_title: str = ""        # Managing Member, CEO, Owner, Managing Partner
    industry: str = ""             # e.g. "marketing agency", "SaaS", "consulting"


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
    # New department outputs
    financial_plan: str = ""
    hr_playbook: str = ""
    sales_playbook: str = ""
    delivery_system: str = ""
    analytics_framework: str = ""
    treasury_plan: str = ""
    tax_playbook: str = ""
    wealth_strategy: str = ""
    # Revenue multiplier outputs
    billing_system: str = ""
    referral_program: str = ""
    upsell_playbook: str = ""
    # Differentiation outputs
    competitive_intel: str = ""
    client_portal: str = ""
    voice_receptionist: str = ""
    # New expansion outputs
    fullstack_dev_output: str = ""
    economist_briefing: str = ""
    pr_communications: str = ""
    data_dashboards: str = ""
    governance_brief: str = ""
    product_roadmap: str = ""
    partnerships_playbook: str = ""
    # Client delivery outputs
    client_fulfillment: str = ""
    # Cognition layer outputs
    agent_workspace: str = ""
    # Cross-campaign intelligence (injected by genome engine at campaign start)
    genome_intel: str = ""

    def entity_rules(self) -> str:
        """Return entity-specific operational rules every agent MUST follow."""
        b = self.business
        et = (b.entity_type or "").lower().replace("-", "_")
        title = b.founder_title or "Owner"
        state = b.state_of_formation or "TBD"

        if not et:
            return ""

        # Base rules every entity gets
        lines = [
            f"\n── ENTITY RULES ({et.upper().replace('_', '-')} · {state}) ──",
            f"Address the founder as \"{title}\". Use that title in all documents, contracts, and communications.",
        ]

        if et == "sole_prop":
            lines += [
                "LEGAL: No corporate veil — owner is personally liable. Emphasize insurance & liability shields.",
                "TAX: All income flows to Schedule C. Self-employment tax applies (15.3%). Recommend quarterly estimated payments.",
                "CONTRACTS: The individual signs, not a company. Use 'DBA' name where applicable.",
                "HIRING: 1099 contractors preferred until revenue justifies payroll burden.",
                "FINANCE: Separate personal/business bank accounts even though not legally required.",
                "COMPLIANCE: Simpler formation but more personal risk. Flag anything that exposes personal assets.",
            ]
        elif et == "llc":
            lines += [
                "LEGAL: Single-member LLC = disregarded entity for tax. Multi-member = partnership. Protect the corporate veil.",
                "TAX: Default pass-through. If profit > $60K, recommend evaluating S-Corp election for SE tax savings.",
                "CONTRACTS: Sign as '[Name], Managing Member of [Company] LLC' — never personal capacity.",
                "HIRING: Can hire W-2 or 1099. Must get EIN before hiring. State-specific employment regs apply.",
                "FINANCE: Operating Agreement is mandatory even for single-member. Separate bank account required.",
                f"COMPLIANCE: Annual report required in {state}. Maintain registered agent. Document all member votes.",
            ]
        elif et == "s_corp":
            lines += [
                "LEGAL: Corp formalities required — minutes, resolutions, officer appointments. Piercing the veil risk if ignored.",
                "TAX: Pass-through but owner MUST take reasonable salary. Remaining profit avoids SE tax. File 1120-S.",
                "CONTRACTS: Sign as '[Name], [Officer Title] of [Company] Inc.' Corporate capacity only.",
                "HIRING: Owner is a W-2 employee. Must run payroll. State payroll tax regs apply.",
                "FINANCE: Reasonable compensation is IRS audit trigger #1. Document salary justification.",
                f"COMPLIANCE: Board minutes, annual report in {state}, S-election maintenance (≤100 shareholders, one class of stock).",
            ]
        elif et == "c_corp":
            lines += [
                "LEGAL: Full corporate formalities — board, officers, minutes, bylaws. Strongest liability protection.",
                "TAX: Double taxation (corp rate 21% + personal on dividends). Justify with reinvestment or investor plans.",
                "CONTRACTS: Sign as officer. Board resolution may be needed for major contracts.",
                "HIRING: Standard W-2 employment. Full benefits deductible at corp level. Owner is employee.",
                "FINANCE: Retained earnings stay in corp. Avoid accumulated earnings tax (>$250K without business purpose).",
                f"COMPLIANCE: Strictest requirements. Annual report in {state}, board meetings, stock ledger, bylaws.",
            ]
        elif et == "partnership":
            lines += [
                "LEGAL: Partners share liability unless LP/LLP. Partnership agreement is CRITICAL.",
                "TAX: Pass-through via K-1s. Self-employment tax on general partner shares. File 1065.",
                "CONTRACTS: Specify which partner(s) have signing authority in partnership agreement.",
                "HIRING: Must have EIN. Partners are not employees — they take guaranteed payments or distributions.",
                "FINANCE: Capital accounts must be tracked. Profit-sharing per agreement, not automatically 50/50.",
                f"COMPLIANCE: Partnership agreement governs. Annual report in {state} if registered as LLP.",
            ]
        else:
            lines.append(f"Entity type '{et}' recognized. Apply general best practices for this structure.")

        return "\n".join(lines)

    def to_context_string(self) -> str:
        b = self.business
        parts = [
            f"BUSINESS: {b.name}",
            f"SERVICE: {b.service}",
            f"ICP: {b.icp}",
            f"GEOGRAPHY: {b.geography}",
            f"GOAL: {b.goal}",
        ]
        if b.entity_type:
            title_label = b.founder_title or "Owner"
            parts.append(f"ENTITY: {b.entity_type.upper().replace('_', '-')} ({b.state_of_formation or 'TBD'})")
            parts.append(f"FOUNDER TITLE: {title_label}")
        if b.industry:
            parts.append(f"INDUSTRY: {b.industry}")
        # Inject entity-specific rules so every agent adapts
        entity_block = self.entity_rules()
        if entity_block:
            parts.append(entity_block)
        if b.brand_context:
            parts.append(f"BRAND CONTEXT: {b.brand_context}")
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
            (self.financial_plan, "FINANCE: plan ready"),
            (self.hr_playbook, "HR: playbook ready"),
            (self.sales_playbook, "SALES: playbook ready"),
            (self.delivery_system, "DELIVERY: system ready"),
            (self.analytics_framework, "ANALYTICS: framework ready"),
            (self.treasury_plan, "TREASURY: plan ready"),
            (self.tax_playbook, "TAX: optimization playbook ready"),
            (self.wealth_strategy, "WEALTH: 1% architecture ready"),
            (self.billing_system, "BILLING: automated invoicing & collection active"),
            (self.referral_program, "REFERRAL: affiliate/referral program active"),
            (self.upsell_playbook, "UPSELL: expansion revenue playbook ready"),
            (self.competitive_intel, "COMPETITIVE INTEL: monitoring active"),
            (self.client_portal, "CLIENT PORTAL: dashboard spec ready"),
            (self.voice_receptionist, "VOICE AI: receptionist system ready"),
            (self.fullstack_dev_output, "FULL-STACK DEV: app/SaaS blueprint ready"),
            (self.economist_briefing, "ECONOMIST: market & macro intelligence ready"),
            (self.pr_communications, "PR & COMMS: media strategy & crisis playbook ready"),
            (self.data_dashboards, "DATA: executive dashboards & agent data layer active"),
            (self.governance_brief, "GOVERNANCE: compliance framework & regulatory monitoring active"),
            (self.product_roadmap, "PRODUCT: roadmap & prioritized backlog ready"),
            (self.partnerships_playbook, "PARTNERSHIPS: BD, UGC & lobbying strategy ready"),
            (self.client_fulfillment, "FULFILLMENT: buyer journey & delivery pipeline active"),
            (self.agent_workspace, "AGENT OPS: compute environments & workflows configured"),
        ]
        for val, label in status_map:
            if val:
                parts.append(label)
        # Inject cross-campaign intelligence from genome engine
        if self.genome_intel:
            parts.append(f"\n── CROSS-CAMPAIGN INTELLIGENCE ──\n{self.genome_intel}")
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


# ── Treasury & Reserve Models ────────────────────────────────────────────────

class ReservePool(BaseModel):
    """A single reserve pool / financial bucket."""
    name: str                          # operating, tax, emergency, growth, owner_pay, retirement, insurance
    target_pct: float = 0.0            # % of revenue allocated here
    target_amount: float = 0.0         # absolute target (e.g. 6 months expenses)
    current_amount: float = 0.0
    account_type: str = ""             # hysa, money_market, t_bill, cd, checking
    institution: str = ""              # bank / brokerage name
    apy: float = 0.0                   # current annual % yield
    auto_sweep: bool = False           # auto-move excess to yield
    last_contribution: Optional[datetime] = None

    @property
    def funded_pct(self) -> float:
        return (self.current_amount / self.target_amount * 100) if self.target_amount else 0.0


class TreasuryConfig(BaseModel):
    """Full treasury configuration for a business."""
    campaign_id: str = ""
    allocation_method: str = "profit_first"  # profit_first, percentage, fixed
    # Profit First buckets (% of revenue)
    profit_pct: float = 5.0
    owner_pay_pct: float = 50.0
    tax_pct: float = 15.0
    operating_pct: float = 30.0
    # Additional reserves
    emergency_target_months: int = 6
    monthly_operating_cost: float = 0.0
    retirement_type: str = ""          # sep_ira, solo_401k, simple_ira, none
    retirement_contribution_pct: float = 0.0
    insurance_reserve_pct: float = 2.0
    # Yield strategy
    yield_strategy: str = "conservative"  # conservative, moderate, aggressive
    pools: list[ReservePool] = []
    total_reserves: float = 0.0
    total_yield_annual: float = 0.0
    last_sweep: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Computer Use / Live Browser Models ──────────────────────────────────────

class BrowserSessionModel(BaseModel):
    """A live browser session with streaming and recording."""
    session_id: str = Field(default_factory=lambda: f"BS-{uuid.uuid4().hex[:12].upper()}")
    agent_id: str = ""
    campaign_id: str = ""
    status: str = "initializing"            # initializing, running, paused, human_control, completed, error
    current_url: str = ""
    page_title: str = ""
    viewport: dict[str, int] = {"width": 1440, "height": 900}
    stream_url: str = ""                    # WebSocket URL for live viewing
    stream_viewers: int = 0
    recording_id: str = ""
    recording_enabled: bool = True
    human_control: bool = False
    handoff_reason: str = ""
    action_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: Optional[datetime] = None


class BrowserActionModel(BaseModel):
    """A single browser interaction step."""
    action_type: str = ""                   # navigate, click, type, scroll, select, hover, etc.
    selector: str = ""                      # CSS/XPath selector
    value: str = ""                         # URL, text, key
    coordinates: Optional[list[int]] = None # [x, y] for vision-guided clicks
    description: str = ""                   # Human-readable explanation
    vision_reasoning: str = ""              # LLM vision model reasoning
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionRecordingModel(BaseModel):
    """A recorded browser session with decision points and annotations."""
    recording_id: str = Field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:12].upper()}")
    session_id: str = ""
    agent_id: str = ""
    campaign_id: str = ""
    frame_count: int = 0
    decision_point_count: int = 0
    annotation_count: int = 0
    total_actions: int = 0
    pages_visited: list[str] = []
    duration_seconds: float = 0.0
    status: str = "recording"               # recording, completed, exported
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VisionAnalysisResult(BaseModel):
    """Result of a vision-guided navigation step."""
    action_type: str = ""                    # Recommended action
    target_description: str = ""             # Human-readable target
    coordinates: Optional[list[int]] = None  # [x, y] pixel coordinates
    value: str = ""                          # Input value
    reasoning: str = ""                      # Why this action
    confidence: float = 0.0                  # 0.0-1.0
    goal_progress: str = ""                  # Progress toward goal
    needs_human: bool = False                # True if stuck
    human_reason: str = ""                   # Why human needed


class HumanHandoffRequest(BaseModel):
    """A request for human takeover of a browser session."""
    session_id: str = ""
    agent_id: str = ""
    campaign_id: str = ""
    reason: str = ""
    current_url: str = ""
    stream_url: str = ""
    notify_channels: list[str] = ["telegram", "slack", "whatsapp"]
    handoff_at: datetime = Field(default_factory=datetime.utcnow)


class BrowserDashboard(BaseModel):
    """Multi-browser control panel state."""
    active_sessions: list[BrowserSessionModel] = []
    active_count: int = 0
    completed_count: int = 0
    max_concurrent: int = 20
    slots_available: int = 20
    recordings_available: int = 0
    total_actions_executed: int = 0
    human_handoffs_active: int = 0


class TreasuryTransaction(BaseModel):
    """Record of money movement between pools."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    from_pool: str = ""                # "revenue", "operating", "growth", etc.
    to_pool: str = ""
    amount: float = 0.0
    reason: str = ""                   # "revenue_allocation", "yield_sweep", "emergency_withdrawal"
    triggered_by: str = ""             # "auto", "treasury_agent", "owner"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Hardware Manufacturing Models ───────────────────────────────────────────

class CADModel(BaseModel):
    """A generated 3D CAD model."""
    model_id: str = Field(default_factory=lambda: f"CAD-{uuid.uuid4().hex[:10].upper()}")
    description: str = ""
    format: str = "step"                    # step, stl, iges, dxf, 3mf
    parameters: dict[str, str] = {}
    material: str = "aluminum_6061"
    dfm_score: float = 0.0
    mass_g: float = 0.0
    bounding_box_mm: dict[str, float] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ManufacturingJob(BaseModel):
    """A manufacturing job — CNC, 3D print, or other process."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    process: str = ""                       # cnc_mill, 3d_print_fdm, injection_mold, sheet_metal, pcb
    machine_id: str = ""
    status: str = "queued"                  # queued, setup, running, inspection, completed, failed
    quantity: int = 1
    material: str = ""
    estimated_time_min: float = 0.0
    actual_time_min: float = 0.0
    cost_per_unit: float = 0.0
    quality_result: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierQuote(BaseModel):
    """A quote from a supplier."""
    quote_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rfq_id: str = ""
    supplier: str = ""
    parts: list[dict[str, Any]] = []
    unit_price: float = 0.0
    total_price: float = 0.0
    lead_time_days: int = 0
    moq: int = 1
    valid_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProductionPlan(BaseModel):
    """A manufacturing production plan."""
    plan_id: str = Field(default_factory=lambda: f"PP-{uuid.uuid4().hex[:8].upper()}")
    product_id: str = ""
    quantity: int = 0
    process: str = ""
    schedule: dict[str, Any] = {}
    resource_allocation: dict[str, Any] = {}
    cost_per_unit: float = 0.0
    total_cost: float = 0.0
    status: str = "draft"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Enterprise Security Models ──────────────────────────────────────────────

class SecurityScan(BaseModel):
    """Result of an automated security scan."""
    scan_id: str = Field(default_factory=lambda: f"SCAN-{uuid.uuid4().hex[:8].upper()}")
    scan_type: str = ""
    target: str = ""
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    compliance_impact: dict[str, str] = {}
    status: str = "completed"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ThreatModelResult(BaseModel):
    """A STRIDE threat model for a system component."""
    component: str = ""
    methodology: str = "stride"
    threats: dict[str, list[dict[str, Any]]] = {}
    agent_specific_threats: list[dict[str, Any]] = []
    overall_risk_score: int = 0
    risk_rating: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceStatus(BaseModel):
    """Compliance posture for a specific framework."""
    framework: str = ""
    total_controls: int = 0
    controls_met: int = 0
    gaps: int = 0
    compliance_pct: float = 0.0
    status: str = ""
    next_audit_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SecurityIncident(BaseModel):
    """A security incident record."""
    incident_id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:8].upper()}")
    severity: str = "medium"
    title: str = ""
    description: str = ""
    status: str = "open"
    assigned_to: str = ""
    mttr_hours: Optional[float] = None
    forensic_data: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class RedTeamResult(BaseModel):
    """Result of adversarial testing against an agent."""
    test_id: str = Field(default_factory=lambda: f"RT-{uuid.uuid4().hex[:8].upper()}")
    agent_id: str = ""
    attack_type: str = ""
    tests_run: int = 0
    blocked: int = 0
    partial_bypass: int = 0
    full_bypass: int = 0
    block_rate_pct: float = 0.0
    agent_hardening_score: int = 0
    findings: list[dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# NVIDIA / AWS / REINDUSTRIALIZATION MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class IoTDeviceModel(BaseModel):
    """Factory floor device registration."""
    device_id: str = ""
    device_type: str = ""  # cnc, printer, sensor, robot, conveyor
    factory_id: str = ""
    status: str = "registered"
    last_telemetry: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RobotFleetStatus(BaseModel):
    """Robot fleet health summary."""
    fleet_id: str = ""
    total_robots: int = 0
    active: int = 0
    maintenance: int = 0
    offline: int = 0
    tasks_completed_today: int = 0
    uptime_pct: float = 0.0


class ReshoringAnalysis(BaseModel):
    """Domestic vs. overseas cost comparison."""
    product: str = ""
    current_source: str = "overseas"
    overseas_landed_cost: float = 0.0
    domestic_cost: float = 0.0
    tariff_risk_premium: float = 0.0
    adjusted_overseas_cost: float = 0.0
    buy_american_compliant: bool = False
    recommendation: str = ""


class FactorySiteAnalysis(BaseModel):
    """Factory site selection scoring."""
    location: str = ""
    overall_score: float = 0.0
    scores: dict[str, float] = {}
    state_incentives: list[dict[str, str]] = []
    workforce_availability: dict[str, int] = {}
    recommendation: str = ""


class GovernmentContract(BaseModel):
    """Defense/government contract opportunity."""
    title: str = ""
    agency: str = ""
    value_est: str = ""
    deadline: str = ""
    set_aside: str = ""
    naics: str = ""
    itar_required: bool = False


class GPUClusterStatus(BaseModel):
    """GPU cluster status summary."""
    total_gpus: int = 0
    allocated: int = 0
    available: int = 0
    avg_utilization_pct: float = 0.0
    active_allocations: int = 0


class DigitalTwinModel(BaseModel):
    """Omniverse digital twin state."""
    twin_id: str = ""
    name: str = ""
    status: str = "created"
    last_simulation: Optional[dict[str, Any]] = None
    sensor_data: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
