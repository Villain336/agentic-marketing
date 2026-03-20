"""Campaign CRUD, run campaign, resume, clone, parallel campaigns, portfolio."""
from __future__ import annotations
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import (
    BusinessProfile, Campaign, CampaignMemory,
    RunCampaignRequest, Tier,
)
from engine import engine
from agents import AGENT_MAP, AGENT_ORDER, get_agent
from scoring import scorer
from genome import genome
from versioning import versioner
from ws import ws_manager
from auth import get_user_id, validate_campaign_id, require_permission, require_auth
from whitelabel import tenant_manager
from store import store, serialize_memory
import db

logger = logging.getLogger("supervisor.api.campaigns")

router = APIRouter(tags=["Campaigns"])


@router.post("/campaign/run")
async def run_campaign(req: RunCampaignRequest, request: Request,
                       user_id: str = Depends(require_permission("campaign", "run_agents"))):
    campaign_id = str(uuid.uuid4())

    # ── Whitelabel: enforce tenant limits and feature flags ──
    tenant = tenant_manager.get_tenant_for_user(user_id)
    if tenant:
        campaign_count = store.campaign_count(user_id)
        limits = tenant_manager.check_limits(tenant, campaign_count, 0)
        if not limits["campaigns_ok"]:
            raise HTTPException(403, f"Campaign limit reached ({limits['campaigns_limit']}). Upgrade your plan.")
        if not tenant_manager.is_feature_enabled(tenant, "multi_campaign") and campaign_count > 0:
            raise HTTPException(403, "Multi-campaign feature not enabled for your plan")

    biz = req.business
    if req.brand_docs and not biz.brand_context:
        biz = BusinessProfile(**{**biz.model_dump(), "brand_context": "\n".join(req.brand_docs)})

    campaign = Campaign(id=campaign_id, user_id=user_id, memory=CampaignMemory(business=biz))
    store.put_campaign(user_id, campaign)

    await db.save_campaign(campaign_id, user_id, serialize_memory(campaign.memory), "active")

    recs = genome.get_recommendations(campaign)
    if recs.get("has_data"):
        intel_lines = []
        for rec in recs.get("recommendations", []):
            intel_lines.append(f"- {rec}")
        if recs.get("benchmarks"):
            benchmarks = recs["benchmarks"]
            intel_lines.append(f"Benchmarks from {recs['matches']} similar campaigns: {benchmarks}")
        campaign.memory.genome_intel = "\n".join(intel_lines)

    agent_ids = AGENT_ORDER
    if req.start_from and req.start_from in AGENT_MAP:
        agent_ids = agent_ids[agent_ids.index(req.start_from):]

    async def stream():
        from engine import run_agents_parallel, AGENT_DEPENDENCIES
        from models import AgentStatus
        yield f"data: {json.dumps({'event': 'campaign_start', 'campaign_id': campaign_id, 'agents': agent_ids})}\n\n"

        agent_list = [get_agent(aid) for aid in agent_ids if get_agent(aid)]
        event_queue = asyncio.Queue()
        parallel_mode = req.__dict__.get("parallel", True) if hasattr(req, '__dict__') else True

        if parallel_mode and len(agent_list) > 1:
            parallel_task = asyncio.create_task(
                run_agents_parallel(
                    agents=agent_list, memory=campaign.memory,
                    campaign_id=campaign_id, campaign=campaign,
                    tier=req.tier, event_queue=event_queue,
                )
            )

            completed_agents = set()
            while not parallel_task.done() or not event_queue.empty():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    if event.memory_update:
                        for k, v in event.memory_update.items():
                            if hasattr(campaign.memory, k):
                                setattr(campaign.memory, k, v)
                    yield f"data: {event.model_dump_json()}\n\n"

                    if event.status == AgentStatus.DONE and event.agent_id not in completed_agents:
                        completed_agents.add(event.agent_id)
                        versioner.snapshot(campaign_id, event.agent_id, serialize_memory(campaign.memory))
                        asyncio.create_task(ws_manager.send_agent_status(campaign_id, event.agent_id, "complete"))
                        asyncio.create_task(db.update_campaign_memory(campaign_id, serialize_memory(campaign.memory)))
                        yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': event.agent_id, 'memory': serialize_memory(campaign.memory)})}\n\n"
                except asyncio.TimeoutError:
                    continue

            results = await parallel_task
            yield f"data: {json.dumps({'event': 'parallel_results', 'results': results})}\n\n"

        else:
            for i, aid in enumerate(agent_ids):
                agent = get_agent(aid)
                if not agent:
                    continue

                yield f"data: {json.dumps({'event': 'agent_start', 'agent_id': aid, 'label': agent.label, 'index': i, 'total': len(agent_ids)})}\n\n"

                try:
                    async for event in engine.run(agent=agent, memory=campaign.memory, campaign_id=campaign_id, tier=req.tier, campaign=campaign):
                        if event.memory_update:
                            for k, v in event.memory_update.items():
                                if hasattr(campaign.memory, k):
                                    setattr(campaign.memory, k, v)
                        yield f"data: {event.model_dump_json()}\n\n"
                except Exception as e:
                    logger.error(f"Campaign agent {aid} failed: {e}", exc_info=True)
                    yield f"data: {json.dumps({'event': 'agent_error', 'agent_id': aid, 'error': str(e)})}\n\n"
                    continue

                versioner.snapshot(campaign_id, aid, serialize_memory(campaign.memory))
                asyncio.create_task(ws_manager.send_agent_status(campaign_id, aid, "complete"))
                await db.update_campaign_memory(campaign_id, serialize_memory(campaign.memory))
                yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid, 'memory': serialize_memory(campaign.memory)})}\n\n"
                await asyncio.sleep(0.5)

        genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
        await db.save_campaign(campaign_id, campaign.user_id, serialize_memory(campaign.memory), "complete")
        yield f"data: {json.dumps({'event': 'campaign_complete', 'campaign_id': campaign_id, 'memory': serialize_memory(campaign.memory)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})


@router.get("/campaign/{campaign_id}")
async def get_campaign(campaign_id: str, request: Request):
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    c = store.get_campaign(user_id, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return {"id": c.id, "status": c.status, "memory": serialize_memory(c.memory), "created_at": c.created_at.isoformat()}


@router.get("/campaign/{campaign_id}/memory")
async def get_memory(campaign_id: str, request: Request):
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    c = store.get_campaign(user_id, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return serialize_memory(c.memory)


@router.get("/campaigns")
async def list_campaigns_from_db(request: Request, offset: int = 0, limit: int = 50):
    """Return all campaigns for the authenticated user from DB (paginated)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    rows = await db.load_user_campaigns(user_id)
    total = len(rows)
    rows = rows[offset:offset + limit]
    result = []
    for row in rows:
        memory_raw = row.get("memory", {})
        if isinstance(memory_raw, str):
            try:
                memory_raw = json.loads(memory_raw)
            except Exception:
                memory_raw = {}
        biz = memory_raw.get("business", {})
        result.append({
            "id": row.get("id", ""),
            "status": row.get("status", "active"),
            "created_at": row.get("created_at", ""),
            "business_name": biz.get("name", ""),
            "agent_count": sum(1 for k, v in memory_raw.items() if k.startswith("has_") and v),
        })
    return {"campaigns": result, "count": len(result), "total": total, "offset": offset, "limit": limit}


@router.get("/campaign/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, request: Request):
    """Load a campaign from DB into memory so the frontend can resume it."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)

    c = store.get_campaign(user_id, campaign_id)
    if c:
        return {
            "id": c.id, "status": c.status,
            "memory": serialize_memory(c.memory),
            "created_at": c.created_at.isoformat(),
            "source": "memory",
        }

    row = await db.load_campaign(campaign_id)
    if not row:
        raise HTTPException(404, "Campaign not found in database")

    if row.get("user_id") and row["user_id"] != user_id:
        raise HTTPException(403, "Not your campaign")

    memory_raw = row.get("memory", {})
    if isinstance(memory_raw, str):
        memory_raw = json.loads(memory_raw)

    biz_data = memory_raw.get("business", {})
    biz = BusinessProfile(**biz_data) if biz_data else BusinessProfile(
        name="", service="", icp="", geography="", goal=""
    )
    mem_fields = {
        k: v for k, v in memory_raw.items()
        if k != "business" and not k.startswith("has_") and hasattr(CampaignMemory, k)
    }
    mem = CampaignMemory(business=biz, **mem_fields)

    campaign = Campaign(
        id=row["id"],
        user_id=row.get("user_id", ""),
        memory=mem,
        status=row.get("status", "active"),
    )
    if row.get("created_at"):
        try:
            campaign.created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        except Exception:
            pass

    store.put_campaign(user_id, campaign)

    return {
        "id": campaign.id, "status": campaign.status,
        "memory": serialize_memory(campaign.memory),
        "created_at": campaign.created_at.isoformat(),
        "source": "database",
    }


@router.delete("/campaign/{campaign_id}")
async def delete_campaign(campaign_id: str, request: Request,
                          user_id: str = Depends(require_permission("campaign", "delete"))):
    validate_campaign_id(campaign_id)
    if store.delete_campaign(user_id, campaign_id):
        return {"deleted": True}
    raise HTTPException(404, "Campaign not found")


class ParallelCampaignRequest(BaseModel):
    clients: list[dict]
    tier: str = "standard"


@router.post("/campaigns/parallel")
async def run_parallel_campaigns(req: ParallelCampaignRequest, request: Request,
                                 user_id: str = Depends(require_permission("campaign", "run_agents"))):
    """Launch multiple campaigns in parallel for different clients."""
    if not req.clients or len(req.clients) < 2:
        raise HTTPException(400, "Provide at least 2 client configs for parallel execution")
    if len(req.clients) > 20:
        raise HTTPException(400, "Maximum 20 parallel campaigns at once")

    tier = Tier(req.tier)
    campaign_ids = []

    for cfg in req.clients:
        biz = BusinessProfile(**cfg["business"])
        campaign_id = str(uuid.uuid4())
        campaign = Campaign(id=campaign_id, memory=CampaignMemory(business=biz))
        campaign.user_id = user_id
        store.put_campaign(user_id, campaign)

        recs = genome.get_recommendations(campaign)
        if recs.get("has_data"):
            intel_lines = [f"- {r}" for r in recs.get("recommendations", [])]
            campaign.memory.genome_intel = "\n".join(intel_lines)

        campaign_ids.append(campaign_id)

    for cid in campaign_ids:
        campaign = store.get_campaign(user_id, cid)
        if campaign:
            asyncio.create_task(_run_campaign_background(campaign, tier))

    return {
        "launched": len(campaign_ids),
        "campaign_ids": campaign_ids,
        "status": "running",
    }


async def _run_campaign_background(campaign: Campaign, tier: Tier):
    """Run a full campaign in the background."""
    for aid in AGENT_ORDER:
        agent = get_agent(aid)
        if not agent:
            continue
        try:
            async for event in engine.run(agent=agent, memory=campaign.memory,
                                          campaign_id=campaign.id, tier=tier, campaign=campaign):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
        except Exception as e:
            logger.error(f"Background campaign {campaign.id} agent {aid} failed: {e}")
            continue
        await asyncio.sleep(1)

    campaign.status = "complete"
    genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
    await db.save_campaign(campaign.id, campaign.user_id,
                           serialize_memory(campaign.memory), "complete")
    logger.info(f"Background campaign {campaign.id} complete")


@router.get("/portfolio")
async def portfolio_overview(request: Request, limit: int = 50, offset: int = 0):
    """Get portfolio-level metrics across all campaigns (paginated)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    user_campaigns = store.list_campaigns(user_id)
    total = len(user_campaigns)

    # Pre-compute all scores in a single batch instead of N+1
    all_scores = {}
    for c in user_campaigns:
        try:
            all_scores[c.id] = scorer.score_all(c)
        except Exception:
            all_scores[c.id] = {}

    healthy = 0
    at_risk = 0
    for cid, scores in all_scores.items():
        avg = sum(d.get("score", 0) for d in scores.values()) / max(len(scores), 1)
        if avg >= 60:
            healthy += 1
        else:
            at_risk += 1

    # Paginate the summaries
    page_campaigns = user_campaigns[offset:offset + limit]
    summaries = []
    for c in page_campaigns:
        scores = all_scores.get(c.id, {})
        avg_score = sum(d.get("score", 0) for d in scores.values()) / max(len(scores), 1)
        summaries.append({
            "id": c.id,
            "business": c.memory.business.name,
            "status": c.status,
            "avg_agent_score": round(avg_score, 1),
            "agents_graded": len(scores),
        })

    return {
        "total_campaigns": total,
        "healthy": healthy,
        "at_risk": at_risk,
        "campaigns": summaries,
        "offset": offset,
        "limit": limit,
    }


class CloneCampaignRequest(BaseModel):
    business_name: str = ""
    service: str = ""
    icp: str = ""
    geography: str = ""
    goal: str = ""
    entity_type: str = ""
    state: str = ""
    industry: str = ""


@router.post("/campaign/{campaign_id}/clone")
async def clone_campaign(campaign_id: str, req: CloneCampaignRequest,
                         request: Request,
                         user_id: str = Depends(require_permission("campaign", "create"))):
    """Clone a successful campaign for a new client.

    HIGH-02 fix: Added require_permission RBAC check (was missing).
    """
    validate_campaign_id(campaign_id)
    source = store.get_campaign(user_id, campaign_id)
    if not source:
        raise HTTPException(404, "Source campaign not found")

    new_biz = BusinessProfile(
        name=req.business_name or "",
        service=req.service or source.memory.business.service,
        icp=req.icp or source.memory.business.icp,
        geography=req.geography or source.memory.business.geography,
        goal=req.goal or source.memory.business.goal,
        entity_type=req.entity_type or source.memory.business.entity_type,
        state_of_formation=req.state or source.memory.business.state_of_formation,
        industry=req.industry or source.memory.business.industry,
    )

    new_id = str(uuid.uuid4())
    new_campaign = Campaign(id=new_id, memory=CampaignMemory(business=new_biz))
    new_campaign.user_id = user_id

    recs = genome.get_recommendations(new_campaign)
    if recs.get("has_data"):
        intel_lines = [f"- {r}" for r in recs.get("recommendations", [])]
        new_campaign.memory.genome_intel = "\n".join(intel_lines)

    store.put_campaign(user_id, new_campaign)

    return {
        "new_campaign_id": new_id,
        "cloned_from": campaign_id,
        "business_name": new_biz.name,
        "genome_intel_injected": bool(new_campaign.memory.genome_intel),
    }


@router.get("/campaign/{campaign_id}/versions")
async def get_memory_versions(campaign_id: str, request: Request, agent_id: str = "", limit: int = 50):
    """Get memory version history for a campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    limit = min(limit, 200)
    return {"versions": versioner.get_history(campaign_id, agent_id, limit)}


@router.get("/campaign/{campaign_id}/versions/{version_id}")
async def get_memory_version(campaign_id: str, version_id: int, request: Request):
    """Get a specific version with full snapshot."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    result = versioner.get_version(campaign_id, version_id)
    if not result:
        raise HTTPException(404, "Version not found")
    return result


@router.get("/campaign/{campaign_id}/versions/diff/{v1}/{v2}")
async def diff_memory_versions(campaign_id: str, v1: int, v2: int, request: Request):
    """Diff two memory versions."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    return versioner.diff_versions(campaign_id, v1, v2)


@router.get("/campaign/{campaign_id}/versions/timeline/{field}")
async def field_timeline(campaign_id: str, field: str, request: Request):
    """Get the change timeline for a specific memory field."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    return {"field": field, "timeline": versioner.get_field_timeline(campaign_id, field)}
