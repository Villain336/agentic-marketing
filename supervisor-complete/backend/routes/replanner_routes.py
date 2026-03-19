"""Dynamic re-planning endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from replanner import replanner

router = APIRouter(prefix="/replanner", tags=["Replanner"])


@router.get("/stats")
async def replanner_stats():
    """Get re-planning statistics."""
    return replanner.get_stats()


@router.get("/history/{campaign_id}/{agent_id}")
async def replanner_history(campaign_id: str, agent_id: str):
    """Get re-planning history for an agent run."""
    history = replanner.get_history(agent_id, campaign_id)
    if not history:
        return {"agent_id": agent_id, "campaign_id": campaign_id, "replans": 0}
    return history.model_dump()
