"""
Phase 2 — Agent Protocol: Open standard for third-party agent integration.

Defines the Omni Agent Protocol (OAP) — a universal interface for registering,
running, and communicating with agents regardless of where they're hosted.

Third-party developers can:
  1. Register external agents with the protocol
  2. Receive execution requests via webhook
  3. Stream results back via callback URL
  4. Publish agents to the marketplace
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from auth import get_user_id, validate_id

logger = logging.getLogger("omnios.protocol")

router = APIRouter(tags=["Agent Protocol"])


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT PROTOCOL SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class AgentCapability(BaseModel):
    """Defines what an agent can do."""
    id: str  # e.g., "web_search", "generate_image", "analyze_data"
    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)  # JSON Schema for inputs
    output_schema: dict = Field(default_factory=dict)  # JSON Schema for outputs


class AgentManifest(BaseModel):
    """The standard manifest every Omni-compatible agent must provide."""
    # Identity
    agent_id: str = Field(default_factory=lambda: f"ext_{uuid4().hex[:12]}")
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    # Classification
    category: str = "general"  # marketing, sales, ops, finance, legal, engineering, intelligence, general
    tags: list[str] = Field(default_factory=list)

    # Capabilities
    capabilities: list[AgentCapability] = Field(default_factory=list)
    tools_required: list[str] = Field(default_factory=list)  # Omni tools this agent needs
    tools_provided: list[str] = Field(default_factory=list)  # tools this agent exposes

    # Execution
    endpoint: str = ""  # HTTPS endpoint for remote execution
    auth_type: str = "api_key"  # api_key, oauth, none
    max_iterations: int = 15
    timeout_seconds: int = 300
    streaming: bool = True  # supports SSE streaming

    # Pricing
    cost_per_run: float = 0.0  # USD
    pricing_model: str = "free"  # free, per_run, subscription

    # Metadata
    icon: str = ""
    documentation_url: str = ""
    source_url: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExternalAgentRegistration(BaseModel):
    """Registry entry for an external agent."""
    id: str = Field(default_factory=lambda: f"reg_{uuid4().hex[:12]}")
    user_id: str = ""
    manifest: AgentManifest
    api_key: str = ""  # key to authenticate with the external agent
    installed_count: int = 0
    approved: bool = False  # marketplace approval status
    listed: bool = False  # visible in marketplace


class AgentExecutionRequest(BaseModel):
    """Standard request format sent to external agents."""
    execution_id: str = Field(default_factory=lambda: f"exec_{uuid4().hex[:12]}")
    agent_id: str
    campaign_id: str = ""
    business_context: dict = Field(default_factory=dict)  # BusinessProfile + memory
    input_data: dict = Field(default_factory=dict)
    callback_url: str = ""  # URL to POST results back to
    streaming_url: str = ""  # SSE endpoint for real-time updates


class AgentExecutionResult(BaseModel):
    """Standard result format returned by external agents."""
    execution_id: str
    agent_id: str
    status: str = "completed"  # completed, failed, timeout
    output: str = ""
    structured_data: dict = Field(default_factory=dict)
    memory_updates: dict = Field(default_factory=dict)
    tools_used: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    cost: float = 0.0


# ── In-memory registry ──────────────────────────────────────────────────

_agent_registry: dict[str, ExternalAgentRegistration] = {}  # reg_id -> registration
_agent_index: dict[str, str] = {}  # agent_id -> reg_id


# ── Protocol Endpoints ──────────────────────────────────────────────────

@router.get("/protocol/spec")
async def get_protocol_spec():
    """Get the Omni Agent Protocol specification."""
    return {
        "protocol": "Omni Agent Protocol (OAP)",
        "version": "1.0.0",
        "description": "Open standard for building and integrating agents with Omni OS",
        "manifest_schema": AgentManifest.model_json_schema(),
        "execution_request_schema": AgentExecutionRequest.model_json_schema(),
        "execution_result_schema": AgentExecutionResult.model_json_schema(),
        "capability_schema": AgentCapability.model_json_schema(),
        "categories": [
            "marketing", "sales", "operations", "finance",
            "legal", "engineering", "intelligence", "general",
        ],
        "auth_types": ["api_key", "oauth", "none"],
        "pricing_models": ["free", "per_run", "subscription"],
        "streaming_format": {
            "type": "SSE (Server-Sent Events)",
            "events": [
                {"event": "think", "data": "Agent reasoning step"},
                {"event": "tool_call", "data": "Tool invocation with name and input"},
                {"event": "tool_result", "data": "Tool execution result"},
                {"event": "output", "data": "Final agent output"},
                {"event": "error", "data": "Error message"},
                {"event": "memory_update", "data": "Campaign memory updates"},
            ],
        },
        "callback_format": {
            "method": "POST",
            "content_type": "application/json",
            "body": "AgentExecutionResult schema",
            "auth": "X-Omni-Signature header with HMAC-SHA256",
        },
    }


@router.post("/protocol/agents/register")
async def register_agent(request: Request):
    """Register an external agent with the Omni platform."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    body = await request.json()
    manifest = AgentManifest(**body.get("manifest", body))

    # Validate endpoint
    if manifest.endpoint and not manifest.endpoint.startswith("https://"):
        raise HTTPException(400, "Agent endpoint must use HTTPS")

    reg = ExternalAgentRegistration(
        user_id=user_id,
        manifest=manifest,
        api_key=body.get("api_key", ""),
    )

    _agent_registry[reg.id] = reg
    _agent_index[manifest.agent_id] = reg.id

    logger.info(f"User {user_id[:8]}... registered agent {manifest.name} ({manifest.agent_id})")

    return {
        "registration_id": reg.id,
        "agent_id": manifest.agent_id,
        "name": manifest.name,
        "status": "registered",
        "listed": reg.listed,
        "message": "Agent registered. Submit for marketplace review to make it public.",
    }


@router.get("/protocol/agents")
async def list_registered_agents(request: Request, category: str = "", listed_only: bool = False):
    """List registered agents. Public agents visible to all, private to owner only."""
    user_id = get_user_id(request)

    results = []
    for reg in _agent_registry.values():
        # Show public agents to everyone, private to owner only
        if listed_only and not reg.listed:
            continue
        if not reg.listed and reg.user_id != user_id:
            continue
        if category and reg.manifest.category != category:
            continue

        results.append({
            "registration_id": reg.id,
            "agent_id": reg.manifest.agent_id,
            "name": reg.manifest.name,
            "version": reg.manifest.version,
            "description": reg.manifest.description,
            "author": reg.manifest.author,
            "category": reg.manifest.category,
            "tags": reg.manifest.tags,
            "capabilities": [c.id for c in reg.manifest.capabilities],
            "pricing_model": reg.manifest.pricing_model,
            "cost_per_run": reg.manifest.cost_per_run,
            "installed_count": reg.installed_count,
            "listed": reg.listed,
            "approved": reg.approved,
        })

    return {"agents": results, "count": len(results)}


@router.get("/protocol/agents/{agent_id}")
async def get_agent_manifest(agent_id: str, request: Request):
    """Get the full manifest for a registered agent."""
    reg_id = _agent_index.get(agent_id)
    if not reg_id:
        raise HTTPException(404, "Agent not found")

    reg = _agent_registry[reg_id]
    user_id = get_user_id(request)
    if not reg.listed and reg.user_id != user_id:
        raise HTTPException(404, "Agent not found")

    return {
        "registration_id": reg.id,
        "manifest": reg.manifest.model_dump(),
        "installed_count": reg.installed_count,
        "listed": reg.listed,
        "approved": reg.approved,
    }


@router.put("/protocol/agents/{agent_id}")
async def update_agent(agent_id: str, request: Request):
    """Update an agent's manifest."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    reg_id = _agent_index.get(agent_id)
    if not reg_id:
        raise HTTPException(404, "Agent not found")

    reg = _agent_registry[reg_id]
    if reg.user_id != user_id:
        raise HTTPException(403, "Not your agent")

    body = await request.json()
    manifest_data = reg.manifest.model_dump()
    manifest_data.update({k: v for k, v in body.items() if k in AgentManifest.model_fields})
    reg.manifest = AgentManifest(**manifest_data)

    return {"agent_id": agent_id, "status": "updated"}


@router.delete("/protocol/agents/{agent_id}")
async def unregister_agent(agent_id: str, request: Request):
    """Unregister an agent from the platform."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    reg_id = _agent_index.get(agent_id)
    if not reg_id:
        raise HTTPException(404, "Agent not found")

    reg = _agent_registry[reg_id]
    if reg.user_id != user_id:
        raise HTTPException(403, "Not your agent")

    _agent_index.pop(agent_id, None)
    del _agent_registry[reg_id]
    return {"agent_id": agent_id, "status": "unregistered"}


@router.post("/protocol/agents/{agent_id}/submit-review")
async def submit_for_review(agent_id: str, request: Request):
    """Submit an agent for marketplace review."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    reg_id = _agent_index.get(agent_id)
    if not reg_id:
        raise HTTPException(404, "Agent not found")

    reg = _agent_registry[reg_id]
    if reg.user_id != user_id:
        raise HTTPException(403, "Not your agent")

    # Auto-approve for now (in production, queue for manual review)
    reg.approved = True
    reg.listed = True

    return {
        "agent_id": agent_id,
        "status": "approved",
        "listed": True,
        "message": "Agent is now visible in the Omni marketplace.",
    }


@router.post("/protocol/execute")
async def execute_external_agent(request: Request):
    """Execute a registered external agent. Proxies the request to the agent's endpoint."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    body = await request.json()
    agent_id = body.get("agent_id", "")
    if not agent_id:
        raise HTTPException(400, "agent_id required")

    reg_id = _agent_index.get(agent_id)
    if not reg_id:
        raise HTTPException(404, "Agent not found in protocol registry")

    reg = _agent_registry[reg_id]
    if not reg.manifest.endpoint:
        raise HTTPException(400, "Agent has no execution endpoint configured")

    exec_req = AgentExecutionRequest(
        agent_id=agent_id,
        campaign_id=body.get("campaign_id", ""),
        business_context=body.get("business_context", {}),
        input_data=body.get("input_data", {}),
        callback_url=body.get("callback_url", ""),
    )

    # Forward to external agent
    import httpx
    headers = {
        "Content-Type": "application/json",
        "X-Omni-Execution-Id": exec_req.execution_id,
        "User-Agent": "OmniOS-Protocol/1.0",
    }
    if reg.api_key:
        headers["Authorization"] = f"Bearer {reg.api_key}"

    try:
        async with httpx.AsyncClient(timeout=reg.manifest.timeout_seconds) as client:
            resp = await client.post(
                reg.manifest.endpoint,
                json=exec_req.model_dump(),
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(502, f"External agent returned {resp.status_code}: {resp.text[:200]}")
    except httpx.TimeoutException:
        raise HTTPException(504, "External agent timed out")
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Failed to reach external agent: {exc}")


@router.post("/protocol/callback")
async def receive_execution_callback(request: Request):
    """Receive execution results from an external agent (callback endpoint)."""
    body = await request.json()
    result = AgentExecutionResult(**body)

    logger.info(f"Received callback for execution {result.execution_id}: {result.status}")

    # TODO: Route result back to the campaign engine, update memory, notify UI
    return {"received": True, "execution_id": result.execution_id}
