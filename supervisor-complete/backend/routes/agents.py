"""Single-agent run, agent debate, and checkpoint endpoints."""
from __future__ import annotations
import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import (
    AgentStreamEvent, BusinessProfile, Campaign, CampaignMemory,
    RunAgentRequest, StepType, Tier,
)
from providers import router as model_router
from engine import engine, get_checkpoint, list_checkpoints
from agents import get_agent
from auth import get_user_id, validate_id
from store import store, serialize_memory

logger = logging.getLogger("supervisor.api.agents")

router = APIRouter(tags=["Agents"])


@router.post("/agent/{agent_id}/run")
async def run_agent(agent_id: str, req: RunAgentRequest, request: Request):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent not found: {agent_id}")

    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    campaign_id = req.campaign_id or str(uuid.uuid4())
    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        campaign = Campaign(id=campaign_id, user_id=user_id,
                            memory=CampaignMemory(business=req.business))
        store.put_campaign(user_id, campaign)

    for key, val in req.memory.items():
        if hasattr(campaign.memory, key):
            setattr(campaign.memory, key, val)

    async def stream():
        try:
            async for event in engine.run(agent=agent, memory=campaign.memory, campaign_id=campaign_id, tier=req.tier, campaign=campaign):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
                yield f"data: {event.model_dump_json()}\n\n"
            yield f"data: {json.dumps({'event': 'campaign_state', 'campaign_id': campaign_id, 'memory': serialize_memory(campaign.memory)})}\n\n"
        except Exception as e:
            logger.error(f"Agent stream error: {e}", exc_info=True)
            yield f"data: {AgentStreamEvent(event=StepType.ERROR, agent_id=agent_id, content=str(e)).model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})


@router.post("/validate")
async def validate_output(request: Request):
    """Validate agent output against simulated buyer personas."""
    body = await request.json()
    output = body.get("output", "")
    icp = body.get("icp", "")
    if not output:
        raise HTTPException(400, "Please provide the 'output' field in request body")

    system = f"""You are a market validation expert. Evaluate this content by simulating 3 buyer personas reacting to it.
Target ICP: {icp}
For each: persona type, reaction, sentiment (positive/negative/skeptical), intent (buy/pass/researching), key objection, specific fix.
End with fit score (0-100) and #1 change to improve."""

    try:
        result = await model_router.complete(
            messages=[{"role": "user", "content": f"Evaluate:\n---\n{output[:3000]}\n---"}],
            system=system, tier=Tier.FAST, max_tokens=2000,
        )
        return {"validation": result["text"], "provider": result["provider"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/validate/gauntlet")
async def gauntlet_validate(request: Request):
    """Run output through the full Persona Gauntlet with structured scoring."""
    from gauntlet import gauntlet
    body = await request.json()
    output = body.get("output", "")
    icp = body.get("icp", "")
    persona_ids = body.get("persona_ids")
    if not output:
        raise HTTPException(400, "Please provide the 'output' field in request body")
    result = await gauntlet.validate(output, icp, persona_ids=persona_ids)
    return result.to_dict()


@router.post("/campaign/{campaign_id}/debate")
async def run_debate(campaign_id: str, request: Request):
    """Run agent debate protocol -- agents review each other's work."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    body = await request.json()
    target_agent_id = body.get("agent_id", "")
    output = body.get("output", "")

    if not output or not target_agent_id:
        raise HTTPException(400, "Must provide agent_id and output to debate")

    reviewer_map = {
        "outreach": ["marketing_expert", "design"],
        "content": ["marketing_expert", "design"],
        "social": ["content", "design"],
        "ads": ["content", "marketing_expert", "design"],
        "newsletter": ["content", "design"],
        "sitelaunch": ["marketing_expert", "design", "content"],
    }
    reviewers = reviewer_map.get(target_agent_id, ["marketing_expert"])

    reviews = []
    for reviewer_id in reviewers:
        try:
            system = f"""You are reviewing the output of the {target_agent_id} agent.
Your role: {reviewer_id}. Campaign context: {campaign.memory.to_context_string()[:1000]}
Review for: brand consistency, messaging alignment, quality, ICP relevance.
Return JSON: {{"approved": true/false, "issues": ["..."], "suggested_changes": ["..."], "score": 0-100}}"""

            result = await model_router.complete(
                messages=[{"role": "user", "content": f"Review this output:\n---\n{output[:3000]}\n---"}],
                system=system, tier=Tier.FAST, max_tokens=1000,
            )
            reviews.append({"reviewer": reviewer_id, "review": result["text"]})
        except Exception as e:
            reviews.append({"reviewer": reviewer_id, "error": str(e)})

    return {"agent_id": target_agent_id, "reviews": reviews, "reviewer_count": len(reviews)}


# ── Checkpoint Endpoints ─────────────────────────────────────────────────────

class ResumeRequest(BaseModel):
    checkpoint_id: str
    tier: Optional[Tier] = None


@router.post("/agent/{agent_id}/resume")
async def resume_agent(agent_id: str, req: ResumeRequest, request: Request):
    """Resume an agent run from a saved mid-execution checkpoint."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    validate_id(agent_id, "agent_id")

    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent not found: {agent_id}")

    checkpoint = get_checkpoint(req.checkpoint_id)
    if not checkpoint:
        raise HTTPException(404, f"Checkpoint not found: {req.checkpoint_id}")

    if checkpoint.get("agent_id") != agent_id:
        raise HTTPException(400, "Checkpoint does not belong to this agent")

    campaign_id = checkpoint.get("campaign_id", "")
    campaign = store.get_campaign(user_id, campaign_id) if campaign_id else None

    async def stream():
        try:
            async for event in engine.resume_from_checkpoint(
                agent=agent,
                checkpoint=checkpoint,
                tier=req.tier,
                campaign=campaign,
            ):
                if event.memory_update and campaign:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
                yield f"data: {event.model_dump_json()}\n\n"
            if campaign and campaign_id:
                yield f"data: {json.dumps({'event': 'campaign_state', 'campaign_id': campaign_id, 'memory': serialize_memory(campaign.memory)})}\n\n"
        except Exception as e:
            logger.error(f"Agent resume stream error: {e}", exc_info=True)
            yield f"data: {AgentStreamEvent(event=StepType.ERROR, agent_id=agent_id, content=str(e)).model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Campaign-ID": campaign_id,
                 "X-Checkpoint-ID": req.checkpoint_id})


@router.get("/agent/{agent_id}/checkpoints")
async def get_agent_checkpoints(agent_id: str, request: Request,
                                campaign_id: str = ""):
    """List available checkpoints for an agent, optionally filtered by campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    validate_id(agent_id, "agent_id")

    # First try in-memory store
    checkpoints = list_checkpoints(agent_id, campaign_id)

    # If none found in memory, try database
    if not checkpoints:
        try:
            import db
            db_rows = await db.load_checkpoints(agent_id, campaign_id)
            checkpoints = [
                {
                    "checkpoint_id": row.get("id", ""),
                    "trace_id": row.get("trace_id", ""),
                    "agent_id": row.get("agent_id", ""),
                    "campaign_id": row.get("campaign_id", ""),
                    "step_number": row.get("step_number", 0),
                    "timestamp": row.get("created_at", ""),
                }
                for row in db_rows
            ]
        except Exception as e:
            logger.debug(f"DB checkpoint load skipped: {e}")

    return {"agent_id": agent_id, "campaign_id": campaign_id,
            "checkpoints": checkpoints, "count": len(checkpoints)}
