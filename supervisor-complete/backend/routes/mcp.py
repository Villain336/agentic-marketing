"""
MCP (Model Context Protocol) Server Interface

Exposes Omni OS tools and resources via MCP-compatible endpoints so that
external MCP clients (e.g. Claude Desktop) can discover and invoke them.

Endpoints:
    POST /mcp/tools/list      — enumerate all registered tools
    POST /mcp/tools/call      — execute a tool by name
    POST /mcp/resources/list  — list available business-data resources
    POST /mcp/resources/read  — read a specific resource
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from tools import registry
from store import store

logger = logging.getLogger("omnios.mcp")

router = APIRouter(prefix="/mcp", tags=["MCP"])


# ── Request / Response schemas ───────────────────────────────────────────────

class ToolCallRequest(BaseModel):
    name: str = Field(..., description="Tool name to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")


class ResourceReadRequest(BaseModel):
    uri: str = Field(..., description="Resource URI to read, e.g. 'campaigns://list'")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tool_def_to_mcp(tool_def) -> dict:
    """Convert an internal ToolDefinition to MCP tool format."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in tool_def.parameters:
        prop: dict[str, Any] = {"type": p.type, "description": p.description}
        if p.enum:
            prop["enum"] = p.enum
        properties[p.name] = prop
        if p.required:
            required.append(p.name)

    return {
        "name": tool_def.name,
        "description": tool_def.description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _build_resource_list() -> list[dict]:
    """Build a list of available MCP resources from the current store."""
    resources: list[dict] = [
        {
            "uri": "campaigns://list",
            "name": "Campaign List",
            "description": "List all active campaigns with their IDs and statuses",
            "mimeType": "application/json",
        },
        {
            "uri": "agents://list",
            "name": "Agent List",
            "description": "List all registered agents and their capabilities",
            "mimeType": "application/json",
        },
        {
            "uri": "tools://list",
            "name": "Tool List",
            "description": "List all registered tool names and categories",
            "mimeType": "application/json",
        },
    ]

    # Add per-campaign resources for each known campaign
    for cid in list(store.campaigns.keys())[:50]:  # cap to avoid huge lists
        resources.append({
            "uri": f"campaigns://{cid}/memory",
            "name": f"Campaign {cid[:8]}... Memory",
            "description": f"Full memory/state for campaign {cid}",
            "mimeType": "application/json",
        })

    return resources


def _read_resource(uri: str) -> dict:
    """Read a resource by URI and return its content."""
    import json
    from agents import AGENTS

    if uri == "campaigns://list":
        campaigns = []
        for cid, campaign in store.campaigns.items():
            campaigns.append({
                "id": cid,
                "business_name": getattr(campaign.memory, "business_name", ""),
                "status": "active" if not getattr(campaign.memory, "campaign_complete", False) else "complete",
            })
        return {"type": "text", "text": json.dumps(campaigns, default=str)}

    if uri == "agents://list":
        agents = []
        for agent_id, agent in AGENTS.items():
            agents.append({
                "id": agent_id,
                "name": getattr(agent, "name", agent_id),
                "description": getattr(agent, "description", ""),
            })
        return {"type": "text", "text": json.dumps(agents, default=str)}

    if uri == "tools://list":
        tools = []
        for tool_def in registry.get_definitions():
            tools.append({
                "name": tool_def.name,
                "category": tool_def.category,
                "description": tool_def.description,
            })
        return {"type": "text", "text": json.dumps(tools, default=str)}

    # campaigns://<id>/memory
    if uri.startswith("campaigns://") and uri.endswith("/memory"):
        parts = uri.replace("campaigns://", "").replace("/memory", "")
        campaign_id = parts
        campaign = store.campaigns.get(campaign_id)
        if not campaign:
            return {"type": "text", "text": json.dumps({"error": f"Campaign {campaign_id} not found"})}
        memory_data = campaign.memory.model_dump() if hasattr(campaign.memory, "model_dump") else {}
        return {"type": "text", "text": json.dumps(memory_data, default=str)}

    return {"type": "text", "text": json.dumps({"error": f"Unknown resource URI: {uri}"})}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/tools/list", summary="List all tools in MCP format")
async def mcp_tools_list():
    """Return all registered Omni OS tools formatted per the MCP specification."""
    tool_defs = registry.get_definitions()
    tools = [_tool_def_to_mcp(td) for td in tool_defs]
    return {"tools": tools}


@router.post("/tools/call", summary="Execute a tool via MCP")
async def mcp_tools_call(req: ToolCallRequest):
    """
    Execute a registered tool by name with the provided arguments.

    Returns MCP-formatted content blocks.
    """
    result = await registry.execute(req.name, req.arguments, call_id="mcp")

    if not result.success:
        return {
            "isError": True,
            "content": [{"type": "text", "text": result.error or "Tool execution failed"}],
        }

    return {
        "content": [{"type": "text", "text": result.output or ""}],
    }


@router.post("/resources/list", summary="List available MCP resources")
async def mcp_resources_list():
    """Return all available business-data resources that MCP clients can read."""
    return {"resources": _build_resource_list()}


@router.post("/resources/read", summary="Read an MCP resource")
async def mcp_resources_read(req: ResourceReadRequest):
    """Read a specific resource by URI and return its content."""
    content = _read_resource(req.uri)
    return {"contents": [{"uri": req.uri, **content}]}
