"""
Supervisor Backend — FastAPI Application
SSE streaming endpoints for real-time agent execution.
"""
from __future__ import annotations
import json
import uuid
import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models import (
    AgentStreamEvent, BusinessProfile, Campaign, CampaignMemory,
    HealthResponse, RunAgentRequest, RunCampaignRequest, StepType, Tier,
)
from providers import router as model_router
from engine import engine
from agents import AGENTS, AGENT_MAP, AGENT_ORDER, get_agent

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("supervisor.api")

app = FastAPI(title="Supervisor API", description="Autonomous Agency Platform — Backend Orchestration", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# In-memory campaign store (swap for Supabase in production)
campaigns: dict[str, Campaign] = {}


def _serialize_memory(m: CampaignMemory) -> dict:
    return {
        "business": m.business.model_dump(),
        "prospect_count": m.prospect_count,
        "has_prospects": bool(m.prospects), "has_outreach": bool(m.email_sequence),
        "has_content": bool(m.content_strategy), "has_social": bool(m.social_calendar),
        "has_ads": bool(m.ad_package), "has_cs": bool(m.cs_system),
        "has_site": bool(m.site_launch_brief), "has_legal": bool(m.legal_playbook),
        "has_gtm": bool(m.gtm_strategy), "has_tools": bool(m.tool_stack),
        "has_newsletter": bool(m.newsletter_system), "has_ppc": bool(m.ppc_playbook),
        "cs_complete": m.cs_complete, "campaign_complete": m.campaign_complete,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH & STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(providers=model_router.status(), active_campaigns=len(campaigns))

@app.get("/agents")
async def list_agents():
    return [{
        "id": a.id, "label": a.label, "role": a.role, "icon": a.icon,
        "tier": a.tier.value, "tool_count": len(a.get_tools()),
        "tool_names": [t.name for t in a.get_tools()], "max_iterations": a.max_iterations,
    } for a in AGENTS]

@app.get("/providers")
async def list_providers():
    return model_router.status()


# ═══════════════════════════════════════════════════════════════════════════════
# RUN SINGLE AGENT — SSE Stream
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/agent/{agent_id}/run")
async def run_agent(agent_id: str, req: RunAgentRequest):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent not found: {agent_id}")

    campaign_id = req.campaign_id or str(uuid.uuid4())
    if campaign_id not in campaigns:
        campaigns[campaign_id] = Campaign(id=campaign_id, memory=CampaignMemory(business=req.business))
    campaign = campaigns[campaign_id]

    for key, val in req.memory.items():
        if hasattr(campaign.memory, key):
            setattr(campaign.memory, key, val)

    async def stream():
        try:
            async for event in engine.run(agent=agent, memory=campaign.memory, campaign_id=campaign_id, tier=req.tier):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
                yield f"data: {event.model_dump_json()}\n\n"
            yield f"data: {json.dumps({'event': 'campaign_state', 'campaign_id': campaign_id, 'memory': _serialize_memory(campaign.memory)})}\n\n"
        except Exception as e:
            logger.error(f"Agent stream error: {e}", exc_info=True)
            yield f"data: {AgentStreamEvent(event=StepType.ERROR, agent_id=agent_id, content=str(e)).model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})


# ═══════════════════════════════════════════════════════════════════════════════
# RUN FULL CAMPAIGN — SSE Stream
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/campaign/run")
async def run_campaign(req: RunCampaignRequest):
    campaign_id = str(uuid.uuid4())
    biz = req.business
    if req.brand_docs and not biz.brand_context:
        biz = BusinessProfile(**{**biz.model_dump(), "brand_context": "\n".join(req.brand_docs)})

    campaign = Campaign(id=campaign_id, memory=CampaignMemory(business=biz))
    campaigns[campaign_id] = campaign

    agent_ids = AGENT_ORDER
    if req.start_from and req.start_from in AGENT_MAP:
        agent_ids = agent_ids[agent_ids.index(req.start_from):]

    async def stream():
        yield f"data: {json.dumps({'event': 'campaign_start', 'campaign_id': campaign_id, 'agents': agent_ids})}\n\n"

        for i, aid in enumerate(agent_ids):
            agent = get_agent(aid)
            if not agent:
                continue

            yield f"data: {json.dumps({'event': 'agent_start', 'agent_id': aid, 'label': agent.label, 'index': i, 'total': len(agent_ids)})}\n\n"

            try:
                async for event in engine.run(agent=agent, memory=campaign.memory, campaign_id=campaign_id, tier=req.tier):
                    if event.memory_update:
                        for k, v in event.memory_update.items():
                            if hasattr(campaign.memory, k):
                                setattr(campaign.memory, k, v)
                    yield f"data: {event.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Campaign agent {aid} failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'event': 'agent_error', 'agent_id': aid, 'error': str(e)})}\n\n"
                continue  # Don't stop campaign on single agent failure

            yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid, 'memory': _serialize_memory(campaign.memory)})}\n\n"
            await asyncio.sleep(1)

        yield f"data: {json.dumps({'event': 'campaign_complete', 'campaign_id': campaign_id, 'memory': _serialize_memory(campaign.memory)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})


# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/campaign/{campaign_id}")
async def get_campaign(campaign_id: str):
    c = campaigns.get(campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return {"id": c.id, "status": c.status, "memory": _serialize_memory(c.memory), "created_at": c.created_at.isoformat()}

@app.get("/campaign/{campaign_id}/memory")
async def get_memory(campaign_id: str):
    c = campaigns.get(campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return _serialize_memory(c.memory)

@app.delete("/campaign/{campaign_id}")
async def delete_campaign(campaign_id: str):
    if campaign_id in campaigns:
        del campaigns[campaign_id]
        return {"deleted": True}
    raise HTTPException(404, "Campaign not found")


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONA VALIDATION BRIDGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/validate")
async def validate_output(request: Request):
    """Validate agent output against simulated buyer personas."""
    body = await request.json()
    output = body.get("output", "")
    icp = body.get("icp", "")
    if not output:
        raise HTTPException(400, "No output to validate")

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


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Supervisor API — {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
