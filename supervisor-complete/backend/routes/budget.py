"""Wallet, budget allocation, spend log, inference costs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from wallet import wallet
from costtracker import cost_tracker
from store import campaigns

router = APIRouter(tags=["Budget"])


@router.post("/campaign/{campaign_id}/budget/allocate")
async def allocate_budget(campaign_id: str, request: Request):
    """Allocate budget to an agent."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    body = await request.json()
    return await wallet.allocate_budget(
        campaign_id, body["agent_id"], body["amount"], body.get("period", "monthly"))


@router.get("/campaign/{campaign_id}/budget")
async def get_budget_summary(campaign_id: str):
    """Get full budget summary for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    return await wallet.get_campaign_summary(campaign_id)


@router.post("/campaign/{campaign_id}/budget/reallocate")
async def reallocate_budget(campaign_id: str, request: Request):
    """Move budget between agents."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    body = await request.json()
    return await wallet.reallocate(
        campaign_id, body["from_agent"], body["to_agent"], body["amount"])


@router.get("/campaign/{campaign_id}/inference-costs")
async def get_inference_costs(campaign_id: str, agent_id: str = ""):
    """Get LLM inference costs for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    if agent_id:
        return cost_tracker.get_agent_cost(campaign_id, agent_id)
    return cost_tracker.get_campaign_cost(campaign_id)


@router.get("/costs")
async def global_costs():
    """Get global LLM inference cost stats."""
    return cost_tracker.get_global_stats()


@router.get("/campaign/{campaign_id}/spend-log")
async def get_spend_log(campaign_id: str, agent_id: str = None):
    """Get spend log for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    return await wallet.get_spend_log(campaign_id, agent_id)
