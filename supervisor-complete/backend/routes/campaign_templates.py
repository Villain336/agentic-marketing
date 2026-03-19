"""Campaign template endpoints."""
from __future__ import annotations
import json
import uuid
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from models import BusinessProfile, Campaign, CampaignMemory, Tier
from engine import engine
from agents import AGENT_MAP, AGENT_ORDER, get_agent
from genome import genome
from versioning import versioner
from auth import get_user_id
from templates import get_template, list_templates
from store import campaigns, serialize_memory
import db

logger = logging.getLogger("supervisor.api.templates")

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("")
async def get_templates():
    """List all available campaign templates."""
    return {"templates": list_templates()}


@router.get("/{template_id}")
async def get_template_detail(template_id: str):
    """Get full template configuration."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    return {"id": template_id, **template}


@router.post("/{template_id}/launch")
async def launch_from_template(template_id: str, request: Request):
    """Launch a campaign from a template — skip onboarding, go straight to execution."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")

    body = await request.json()

    biz_data = {**template.get("business_defaults", {}), **body.get("business", {})}
    biz = BusinessProfile(**{
        "name": biz_data.get("name", ""),
        "service": biz_data.get("service", ""),
        "icp": biz_data.get("icp", ""),
        "geography": biz_data.get("geography", ""),
        "goal": biz_data.get("goal", template.get("business_defaults", {}).get("goal", "")),
        "entity_type": biz_data.get("entity_type", ""),
        "state_of_formation": biz_data.get("state_of_formation", ""),
        "industry": biz_data.get("industry", ""),
        "brand_context": biz_data.get("brand_context", ""),
    })

    campaign_id = str(uuid.uuid4())
    campaign = Campaign(id=campaign_id, memory=CampaignMemory(business=biz))
    campaign.user_id = get_user_id(request)
    campaigns[campaign_id] = campaign

    recs = genome.get_recommendations(campaign)
    if recs.get("has_data"):
        intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
        campaign.memory.genome_intel = "\n".join(intel_lines)

    if template.get("agents") == "all":
        agent_ids = AGENT_ORDER
    else:
        agent_ids = [a for a in template["agents"] if a in AGENT_MAP]

    tier = Tier(body.get("tier", "standard"))

    async def stream():
        yield f"data: {json.dumps({'event': 'template_launch', 'template': template_id, 'campaign_id': campaign_id, 'agents': agent_ids})}\n\n"

        for i, aid in enumerate(agent_ids):
            agent = get_agent(aid)
            if not agent:
                continue

            yield f"data: {json.dumps({'event': 'agent_start', 'agent_id': aid, 'label': agent.label, 'index': i, 'total': len(agent_ids)})}\n\n"

            try:
                async for event in engine.run(agent=agent, memory=campaign.memory,
                                              campaign_id=campaign_id, tier=tier, campaign=campaign):
                    if event.memory_update:
                        for k, v in event.memory_update.items():
                            if hasattr(campaign.memory, k):
                                setattr(campaign.memory, k, v)
                    yield f"data: {event.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Template campaign agent {aid} failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'event': 'agent_error', 'agent_id': aid, 'error': str(e)})}\n\n"
                continue

            versioner.snapshot(campaign_id, aid, serialize_memory(campaign.memory))
            yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid, 'memory': serialize_memory(campaign.memory)})}\n\n"
            await asyncio.sleep(1)

        genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
        await db.save_campaign(campaign_id, campaign.user_id,
                               serialize_memory(campaign.memory), "complete")
        yield f"data: {json.dumps({'event': 'campaign_complete', 'campaign_id': campaign_id, 'template': template_id, 'memory': serialize_memory(campaign.memory)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})
