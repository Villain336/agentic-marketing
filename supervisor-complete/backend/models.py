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
