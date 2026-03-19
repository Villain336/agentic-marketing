"""On-prem / local deployment endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from onprem import onprem
from auth import get_user_id

router = APIRouter(prefix="/deployment", tags=["Deployment"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.get("/status")
async def deployment_status():
    """Get current deployment mode and configuration (public)."""
    return onprem.health_check()


@router.post("/configure")
async def configure_deployment(request: Request):
    """Update deployment mode (cloud/hybrid/onprem/airgap)."""
    _require_auth(request)
    body = await request.json()
    mode = onprem.configure_mode(body.pop("mode", "cloud"), **body)
    return mode.model_dump()


@router.post("/local-llm")
async def register_local_llm(request: Request):
    """Register a local LLM endpoint."""
    _require_auth(request)
    body = await request.json()
    from onprem import LocalLLMConfig
    config = LocalLLMConfig(**body)
    result = onprem.register_local_llm(config)
    return result.model_dump()


@router.post("/local-llm/preset/{preset_name}")
async def register_llm_preset(preset_name: str, request: Request):
    """Register a pre-configured local LLM (ollama_llama3, ollama_mixtral, etc.)."""
    _require_auth(request)
    result = onprem.register_preset(preset_name)
    if not result:
        raise HTTPException(404, f"Preset not found: {preset_name}")
    return result.model_dump()


@router.get("/local-llms")
async def list_local_llms(request: Request):
    """List registered local LLMs."""
    _require_auth(request)
    return {"llms": [l.model_dump() for l in onprem.get_local_llms()]}


@router.get("/blocked-tools")
async def get_blocked_tools():
    """Get tools blocked by current deployment mode (public)."""
    return {"blocked": onprem.get_blocked_tools(), "mode": onprem.deployment_mode.mode}


@router.post("/retention")
async def set_retention_policy(request: Request):
    """Set data retention policy."""
    _require_auth(request)
    body = await request.json()
    from onprem import DataRetentionPolicy
    policy = DataRetentionPolicy(**body)
    onprem.set_retention_policy(policy)
    return policy.model_dump()


@router.get("/export")
async def export_deployment_config(request: Request):
    """Export on-prem configuration for backup."""
    _require_auth(request)
    return onprem.export_config()
