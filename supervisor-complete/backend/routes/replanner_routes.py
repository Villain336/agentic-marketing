"""Dynamic re-planning endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from replanner import replanner
from auth import get_user_id

router = APIRouter(prefix="/replanner", tags=["Replanner"])


@router.get("/stats")
async def replanner_stats(request: Request):
    """Get re-planning statistics."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return replanner.get_stats()


@router.get("/history/{campaign_id}/{agent_id}")
async def replanner_history(campaign_id: str, agent_id: str, request: Request):
    """Get re-planning history for an agent run."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    history = replanner.get_history(agent_id, campaign_id)
    if not history:
        return {"agent_id": agent_id, "campaign_id": campaign_id, "replans": 0}
    return history.model_dump()
