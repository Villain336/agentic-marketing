"""Health, status, and system introspection endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from models import HealthResponse
from providers import router as model_router
from agents import AGENTS
from scheduler import scheduler
from ws import ws_manager
from store import store

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(providers=model_router.status(), active_campaigns=store.campaign_count())


@router.get("/agents")
async def list_agents():
    return [{
        "id": a.id, "label": a.label, "role": a.role, "icon": a.icon,
        "tier": a.tier.value, "tool_count": len(a.get_tools()),
        "tool_names": [t.name for t in a.get_tools()], "max_iterations": a.max_iterations,
    } for a in AGENTS]


@router.get("/providers")
async def list_providers():
    return model_router.status()


@router.get("/scheduler")
async def scheduler_status():
    """Get status of all scheduled background jobs."""
    return {"jobs": scheduler.get_status()}


@router.get("/ws/status")
async def ws_status():
    """Get WebSocket connection stats."""
    return ws_manager.get_status()
