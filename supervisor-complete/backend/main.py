"""
Supervisor Backend — FastAPI Application
SSE streaming endpoints for real-time agent execution.
Includes: onboarding, webhooks, approvals, scoring, wallet, gauntlet.
"""
from __future__ import annotations
import json
import uuid
import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models import (
    AgentStreamEvent, ApprovalItem, BusinessProfile, Campaign, CampaignMemory,
    HealthResponse, OnboardingProfile, PerformanceEvent, RunAgentRequest,
    RunCampaignRequest, StepType, Tier,
)
from providers import router as model_router
from engine import engine
from agents import AGENTS, AGENT_MAP, AGENT_ORDER, BACKOFFICE_LAYER, REVENUE_LAYER, get_agent
from scoring import scorer
from sensing import sensing
from wallet import wallet
from gauntlet import gauntlet
from genome import genome
from scheduler import scheduler, register_default_jobs
from auth import AuthMiddleware, get_user_id
from lifecycle import lifecycle
import db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("supervisor.api")

app = FastAPI(title="Supervisor API", description="Autonomous Agency Platform — Backend Orchestration", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(AuthMiddleware)


@app.on_event("startup")
async def startup_event():
    """Start background scheduler with default jobs."""
    register_default_jobs()
    scheduler.start()
    logger.info("Background scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scheduler."""
    scheduler.stop()
    logger.info("Background scheduler stopped")

# In-memory stores (swap for Supabase in production)
campaigns: dict[str, Campaign] = {}
onboarding_profiles: dict[str, OnboardingProfile] = {}
approval_queue: dict[str, ApprovalItem] = {}


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
        "has_finance": bool(m.financial_plan), "has_hr": bool(m.hr_playbook),
        "has_sales": bool(m.sales_playbook), "has_delivery": bool(m.delivery_system),
        "has_analytics": bool(m.analytics_framework),
        "has_tax": bool(m.tax_playbook), "has_wealth": bool(m.wealth_strategy),
        "has_billing": bool(m.billing_system), "has_referral": bool(m.referral_program),
        "has_upsell": bool(m.upsell_playbook),
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

@app.get("/scheduler")
async def scheduler_status():
    """Get status of all scheduled background jobs."""
    return {"jobs": scheduler.get_status()}


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

    # Inject cross-campaign intelligence from genome engine
    recs = genome.get_recommendations(campaign)
    if recs.get("has_data"):
        intel_lines = []
        for rec in recs.get("recommendations", []):
            intel_lines.append(f"• {rec}")
        if recs.get("benchmarks"):
            benchmarks = recs["benchmarks"]
            intel_lines.append(f"Benchmarks from {recs['matches']} similar campaigns: {benchmarks}")
        campaign.memory.genome_intel = "\n".join(intel_lines)

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
                continue

            yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid, 'memory': _serialize_memory(campaign.memory)})}\n\n"
            await asyncio.sleep(1)

        # Record campaign DNA for cross-campaign learning
        genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
        # Persist to database
        await db.save_campaign(campaign_id, campaign.user_id, _serialize_memory(campaign.memory), "complete")
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
# PERSONA VALIDATION (Legacy + Gauntlet)
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


@app.post("/validate/gauntlet")
async def gauntlet_validate(request: Request):
    """Run output through the full Persona Gauntlet with structured scoring."""
    body = await request.json()
    output = body.get("output", "")
    icp = body.get("icp", "")
    persona_ids = body.get("persona_ids")
    if not output:
        raise HTTPException(400, "No output to validate")
    result = await gauntlet.validate(output, icp, persona_ids=persona_ids)
    return result.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/onboarding/create")
async def create_onboarding(request: Request):
    """Create a new onboarding profile."""
    body = await request.json()
    profile = OnboardingProfile(user_id=body.get("user_id", ""))
    onboarding_profiles[profile.id] = profile
    return {"id": profile.id, "current_stage": profile.current_stage}


@app.get("/onboarding/{profile_id}")
async def get_onboarding(profile_id: str):
    """Get onboarding profile state."""
    profile = onboarding_profiles.get(profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")
    return profile.model_dump()


@app.post("/onboarding/{profile_id}/stage/{stage}")
async def update_onboarding_stage(profile_id: str, stage: int, request: Request):
    """Update a specific onboarding stage with data."""
    profile = onboarding_profiles.get(profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    body = await request.json()

    if stage == 1:  # Vision Interview
        from models import BusinessBrief
        profile.business_brief = BusinessBrief(**body.get("business_brief", {}))
    elif stage == 2:  # Mood Board / Visual DNA
        from models import VisualDNA
        profile.visual_dna = VisualDNA(**body.get("visual_dna", {}))
        profile.mood_board_references = body.get("reference_urls", [])
    elif stage == 3:  # Business Formation
        from models import FormationProfile
        profile.formation = FormationProfile(**body.get("formation", {}))
    elif stage == 4:  # Revenue Architecture
        from models import RevenueModel
        profile.revenue_model = RevenueModel(**body.get("revenue_model", {}))
    elif stage == 5:  # Channel Setup
        profile.channels = body.get("channels", {})
    elif stage == 6:  # Market Deep Dive
        profile.market_research = body.get("market_research", {})
    elif stage == 7:  # Autonomy Configuration
        from models import AutonomyConfig
        profile.autonomy = AutonomyConfig(**body.get("autonomy", {}))

    if stage not in profile.completed_stages:
        profile.completed_stages.append(stage)
    profile.current_stage = min(stage + 1, 7)

    return {"updated": True, "current_stage": profile.current_stage,
            "completed_stages": profile.completed_stages}


@app.post("/onboarding/{profile_id}/vision-interview")
async def run_vision_interview(profile_id: str, request: Request):
    """Run the Vision Interview agent for Stage 1 onboarding — SSE stream."""
    profile = onboarding_profiles.get(profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    body = await request.json()
    user_message = body.get("message", "")
    agent = get_agent("vision_interview")
    if not agent:
        raise HTTPException(500, "Vision Interview agent not configured")

    # Create a temporary campaign for the interview
    biz = BusinessProfile(
        name=profile.business_brief.name or "New Agency",
        service=profile.business_brief.service_definition or user_message,
        icp="", geography="", goal="",
    )
    memory = CampaignMemory(business=biz)

    async def stream():
        try:
            async for event in engine.run(agent=agent, memory=memory, campaign_id=profile_id):
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:
            yield f"data: {AgentStreamEvent(event=StepType.ERROR, agent_id='vision_interview', content=str(e)).model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.post("/onboarding/crawl-url")
async def crawl_url(request: Request):
    """Crawl a URL and extract visual signals for mood board (Stage 2)."""
    body = await request.json()
    url = body.get("url", "")
    if not url:
        raise HTTPException(400, "No URL provided")

    # Use web_scrape tool + LLM vision analysis
    from tools import registry
    scrape_result = await registry.execute("web_scrape", {"url": url, "max_chars": 5000}, "crawl")

    # Analyze with LLM
    try:
        result = await model_router.complete(
            messages=[{"role": "user",
                       "content": f"Analyze this website's visual design. URL: {url}\nContent: {scrape_result.output[:3000]}\n\nExtract: dominant colors (hex), typography style, layout pattern, photography style, vibe keywords. Return as JSON."}],
            system="You are a visual design analyst. Return structured JSON with: dominant_colors, typography_classification, layout_pattern, photography_style, vibe_keywords.",
            tier=Tier.FAST, max_tokens=1000,
        )
        return {"url": url, "analysis": result["text"], "raw_content": scrape_result.output[:1000]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/onboarding/search-references")
async def search_references(request: Request):
    """Search for visual reference sites in an industry (Stage 2)."""
    body = await request.json()
    query = body.get("query", "")
    industry = body.get("industry", "")
    if not query:
        raise HTTPException(400, "No search query provided")

    from tools import registry
    search_result = await registry.execute("web_search",
        {"query": f"best {industry} website design {query}", "num_results": 5}, "search")
    return {"query": query, "results": json.loads(search_result.output) if search_result.success else {"error": search_result.error}}


@app.post("/onboarding/generate-visual-dna")
async def generate_visual_dna(request: Request):
    """Generate a Visual DNA profile from collected references (Stage 2)."""
    body = await request.json()
    references = body.get("references", [])
    if not references:
        raise HTTPException(400, "No references provided")

    try:
        result = await model_router.complete(
            messages=[{"role": "user",
                       "content": f"Analyze these visual references and generate a complete Visual DNA profile:\n{json.dumps(references, indent=2)}"}],
            system="""You are a senior creative director. Analyze the visual references and produce a Visual DNA profile as JSON:
{
  "color_palette": {"primary": "#hex", "secondary": "#hex", "accent": "#hex", "neutrals": ["#hex", ...]},
  "typography": {"display_font": "name", "body_font": "name", "mono_font": "name"},
  "photography_direction": "description",
  "illustration_style": "description or None",
  "layout_preferences": "description",
  "density": "sparse|balanced|dense",
  "brand_personality": "description",
  "anti_patterns": ["things to never do"]
}""",
            tier=Tier.STANDARD, max_tokens=2000,
        )
        return {"visual_dna": result["text"]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/onboarding/{profile_id}/market-research")
async def run_market_research(profile_id: str):
    """Run market research agents during onboarding (Stage 6) — SSE stream."""
    profile = onboarding_profiles.get(profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    biz = BusinessProfile(
        name=profile.business_brief.name or "Agency",
        service=profile.business_brief.service_definition or "",
        icp=profile.business_brief.icp_firmographic or "",
        geography="", goal="",
    )
    memory = CampaignMemory(business=biz)

    # Run marketing_expert, limited prospector, and content in sequence
    research_agents = ["marketing_expert", "prospector", "content"]

    async def stream():
        yield f"data: {json.dumps({'event': 'research_start', 'agents': research_agents})}\n\n"
        for aid in research_agents:
            agent = get_agent(aid)
            if not agent:
                continue
            yield f"data: {json.dumps({'event': 'agent_start', 'agent_id': aid, 'label': agent.label})}\n\n"
            try:
                async for event in engine.run(agent=agent, memory=memory, campaign_id=profile_id):
                    if event.memory_update:
                        for k, v in event.memory_update.items():
                            if hasattr(memory, k):
                                setattr(memory, k, v)
                    yield f"data: {event.model_dump_json()}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'event': 'agent_error', 'agent_id': aid, 'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid})}\n\n"
        yield f"data: {json.dumps({'event': 'research_complete'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK RECEIVER
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    """Universal webhook receiver for external services."""
    body = await request.json()
    campaign_id = body.get("campaign_id", "")

    # Find campaign — try body, then headers, then first active
    if not campaign_id:
        campaign_id = request.headers.get("X-Campaign-ID", "")
    if not campaign_id and campaigns:
        campaign_id = next(iter(campaigns))

    campaign = campaigns.get(campaign_id)
    if not campaign:
        logger.warning(f"Webhook from {source} but no matching campaign")
        return {"received": True, "processed": False, "reason": "no matching campaign"}

    event = PerformanceEvent(campaign_id=campaign_id, source=source,
                              event_type=body.get("event", body.get("type", "")),
                              data=body)

    # Persist webhook event to database
    await db.save_performance_event({
        "id": event.id, "campaign_id": campaign_id, "source": source,
        "event_type": event.event_type, "data": body,
    })

    trigger = await sensing.process_event(campaign, event)

    result = {"received": True, "processed": True, "source": source}
    if trigger:
        result["trigger"] = trigger
        logger.info(f"Webhook trigger: {trigger}")
        # Actually execute the triggered agent re-run in the background
        if trigger.get("trigger") == "rerun_agent":
            agent_id = trigger.get("agent_id")
            reason = trigger.get("reason", "threshold breach")
            asyncio.create_task(
                _execute_sensing_trigger(campaign, agent_id, reason)
            )
            result["action"] = f"Scheduled re-run of {agent_id}"

    return result


async def _execute_sensing_trigger(campaign: Campaign, agent_id: str, reason: str):
    """Background task: re-run an agent after a sensing trigger fires."""
    agent = get_agent(agent_id)
    if not agent:
        logger.error(f"Sensing trigger: agent {agent_id} not found")
        return

    logger.info(f"Sensing trigger executing: re-running {agent_id} — {reason}")

    # Inject the trigger reason into memory so the agent knows why it's re-running
    campaign.memory.brand_context = (
        (campaign.memory.business.brand_context or "")
        + f"\n\n[AUTO-TRIGGER] You are re-running because: {reason}. "
        f"Review your previous output and optimize based on the new performance data."
    )

    try:
        async for event in engine.run(
            agent=agent, memory=campaign.memory,
            campaign_id=campaign.id, tier=Tier.STANDARD,
        ):
            if event.memory_update:
                for k, v in event.memory_update.items():
                    if hasattr(campaign.memory, k):
                        setattr(campaign.memory, k, v)
        logger.info(f"Sensing trigger complete: {agent_id} re-run finished")
    except Exception as e:
        logger.error(f"Sensing trigger failed for {agent_id}: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/approvals")
async def list_approvals(status: str = "pending"):
    """List approval queue items filtered by status."""
    items = [a.model_dump() for a in approval_queue.values() if a.status == status]
    return {"items": items, "count": len(items)}


@app.post("/approvals")
async def create_approval(request: Request):
    """Create a new approval request."""
    body = await request.json()
    item = ApprovalItem(
        campaign_id=body.get("campaign_id", ""),
        agent_id=body.get("agent_id", ""),
        action_type=body.get("action_type", ""),
        content=body.get("content", {}),
    )
    approval_queue[item.id] = item
    return {"id": item.id, "status": "pending"}


@app.post("/approvals/{item_id}/decide")
async def decide_approval(item_id: str, request: Request):
    """Approve or reject an item in the approval queue."""
    item = approval_queue.get(item_id)
    if not item:
        raise HTTPException(404, "Approval item not found")

    body = await request.json()
    decision = body.get("decision", "")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "Decision must be 'approved' or 'rejected'")

    item.status = decision
    item.decided_by = body.get("decided_by", "human")
    item.decided_at = datetime.utcnow()

    return {"id": item_id, "status": item.status, "decided_by": item.decided_by}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SCORING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/campaign/{campaign_id}/scores")
async def get_campaign_scores(campaign_id: str):
    """Get performance scores for all agents in a campaign."""
    campaign = campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return scorer.score_all(campaign)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT WALLET & BUDGET
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/campaign/{campaign_id}/budget/allocate")
async def allocate_budget(campaign_id: str, request: Request):
    """Allocate budget to an agent."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    body = await request.json()
    return await wallet.allocate_budget(
        campaign_id, body["agent_id"], body["amount"], body.get("period", "monthly"))


@app.get("/campaign/{campaign_id}/budget")
async def get_budget_summary(campaign_id: str):
    """Get full budget summary for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    return await wallet.get_campaign_summary(campaign_id)


@app.post("/campaign/{campaign_id}/budget/reallocate")
async def reallocate_budget(campaign_id: str, request: Request):
    """Move budget between agents."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    body = await request.json()
    return await wallet.reallocate(
        campaign_id, body["from_agent"], body["to_agent"], body["amount"])


@app.get("/campaign/{campaign_id}/spend-log")
async def get_spend_log(campaign_id: str, agent_id: str = None):
    """Get spend log for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    return await wallet.get_spend_log(campaign_id, agent_id)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT DEBATE PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/campaign/{campaign_id}/debate")
async def run_debate(campaign_id: str, request: Request):
    """Run agent debate protocol — agents review each other's work."""
    campaign = campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    body = await request.json()
    target_agent_id = body.get("agent_id", "")
    output = body.get("output", "")

    if not output or not target_agent_id:
        raise HTTPException(400, "Must provide agent_id and output to debate")

    # Define reviewers based on target agent
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


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-CAMPAIGN ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/campaigns")
async def list_campaigns(request: Request):
    """List all campaigns, optionally filtered by user."""
    user_id = get_user_id(request)
    if user_id and user_id != "dev-mode":
        return {"campaigns": [
            {"id": c.id, "status": c.status, "created_at": c.created_at.isoformat(),
             "business": c.memory.business.name}
            for c in campaigns.values() if c.user_id == user_id
        ]}
    return {"campaigns": [
        {"id": c.id, "status": c.status, "created_at": c.created_at.isoformat(),
         "business": c.memory.business.name}
        for c in campaigns.values()
    ]}


@app.post("/campaigns/parallel")
async def run_parallel_campaigns(request: Request):
    """Launch multiple campaigns in parallel for different clients — shared genome intelligence."""
    body = await request.json()
    client_configs = body.get("clients", [])
    if not client_configs or len(client_configs) < 2:
        raise HTTPException(400, "Provide at least 2 client configs for parallel execution")

    tier = Tier(body.get("tier", "standard"))
    campaign_ids = []

    for cfg in client_configs:
        biz = BusinessProfile(**cfg["business"])
        campaign_id = str(uuid.uuid4())
        campaign = Campaign(id=campaign_id, memory=CampaignMemory(business=biz))
        campaign.user_id = get_user_id(request)
        campaigns[campaign_id] = campaign

        # Inject genome intelligence
        recs = genome.get_recommendations(campaign)
        if recs.get("has_data"):
            intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
            campaign.memory.genome_intel = "\n".join(intel_lines)

        campaign_ids.append(campaign_id)

    # Launch all campaigns as background tasks
    for cid in campaign_ids:
        campaign = campaigns[cid]
        asyncio.create_task(_run_campaign_background(campaign, tier))

    return {
        "launched": len(campaign_ids),
        "campaign_ids": campaign_ids,
        "status": "running",
        "genome_cross_pollination": True,
    }


async def _run_campaign_background(campaign: Campaign, tier: Tier):
    """Run a full campaign in the background."""
    for aid in AGENT_ORDER:
        agent = get_agent(aid)
        if not agent:
            continue
        try:
            async for event in engine.run(agent=agent, memory=campaign.memory,
                                          campaign_id=campaign.id, tier=tier):
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
                           _serialize_memory(campaign.memory), "complete")
    logger.info(f"Background campaign {campaign.id} complete")


@app.get("/portfolio")
async def portfolio_overview(request: Request):
    """Get portfolio-level metrics across all campaigns."""
    user_id = get_user_id(request)
    user_campaigns = [c for c in campaigns.values()
                      if not user_id or user_id == "dev-mode" or c.user_id == user_id]

    total_mrr = 0
    healthy = 0
    at_risk = 0

    summaries = []
    for c in user_campaigns:
        scores = scorer.score_all(c)
        avg_score = sum(d.get("score", 0) for d in scores.values()) / max(len(scores), 1)
        if avg_score >= 60:
            healthy += 1
        else:
            at_risk += 1

        summaries.append({
            "id": c.id,
            "business": c.memory.business.name,
            "status": c.status,
            "avg_agent_score": round(avg_score, 1),
            "agents_graded": len(scores),
        })

    return {
        "total_campaigns": len(user_campaigns),
        "healthy": healthy,
        "at_risk": at_risk,
        "campaigns": summaries,
    }


@app.post("/campaign/{campaign_id}/clone")
async def clone_campaign(campaign_id: str, request: Request):
    """Clone a successful campaign for a new client."""
    source = campaigns.get(campaign_id)
    if not source:
        raise HTTPException(404, "Source campaign not found")

    body = await request.json()
    new_biz = BusinessProfile(
        name=body.get("business_name", ""),
        service=body.get("service", source.memory.business.service),
        icp=body.get("icp", source.memory.business.icp),
        geography=body.get("geography", source.memory.business.geography),
        goal=body.get("goal", source.memory.business.goal),
        entity_type=body.get("entity_type", source.memory.business.entity_type),
        state_of_formation=body.get("state", source.memory.business.state_of_formation),
        industry=body.get("industry", source.memory.business.industry),
    )

    new_id = str(uuid.uuid4())
    new_campaign = Campaign(id=new_id, memory=CampaignMemory(business=new_biz))
    new_campaign.user_id = get_user_id(request)

    # Inject genome intelligence from all past campaigns (including source)
    recs = genome.get_recommendations(new_campaign)
    if recs.get("has_data"):
        intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
        new_campaign.memory.genome_intel = "\n".join(intel_lines)

    campaigns[new_id] = new_campaign

    return {
        "new_campaign_id": new_id,
        "cloned_from": campaign_id,
        "business_name": new_biz.name,
        "genome_intel_injected": bool(new_campaign.memory.genome_intel),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT LIFECYCLE — A/B Testing, Health, Dissolution
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/campaign/{campaign_id}/health")
async def campaign_health(campaign_id: str):
    """Evaluate agent health across a campaign."""
    campaign = campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return lifecycle.evaluate_health(campaign)


@app.get("/campaign/{campaign_id}/lifecycle/recommendations")
async def lifecycle_recommendations(campaign_id: str):
    """Get dissolution/A/B test recommendations for underperforming agents."""
    campaign = campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return {"recommendations": lifecycle.recommend_dissolution(campaign)}


@app.post("/lifecycle/ab-test")
async def create_ab_test(request: Request):
    """Create an A/B test between agent variants."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    variants = body.get("variants", [])
    if not agent_id or len(variants) < 2:
        raise HTTPException(400, "Need agent_id and at least 2 variants")

    test = lifecycle.create_ab_test(
        agent_id=agent_id,
        variant_configs=variants,
        min_runs=body.get("min_runs", 3),
        auto_promote=body.get("auto_promote", True),
    )
    return test.to_dict()


@app.get("/lifecycle/ab-test/{test_id}")
async def get_ab_test(test_id: str):
    """Get A/B test status and results."""
    result = lifecycle.get_test(test_id)
    if not result:
        raise HTTPException(404, "Test not found")
    return result


@app.post("/lifecycle/ab-test/{test_id}/result")
async def record_ab_result(test_id: str, request: Request):
    """Record a variant run result."""
    body = await request.json()
    winner = lifecycle.record_test_result(
        test_id, body.get("variant_id", ""), body.get("score", 0),
    )
    return {"recorded": True, "winner_id": winner}


@app.get("/lifecycle/tests")
async def list_ab_tests(agent_id: str = ""):
    """List all A/B tests, optionally filtered by agent."""
    return {"tests": lifecycle.list_tests(agent_id)}


@app.post("/lifecycle/dissolve")
async def dissolve_agent(request: Request):
    """Dissolve an underperforming agent in a campaign."""
    body = await request.json()
    result = lifecycle.dissolve_agent(
        body.get("agent_id", ""), body.get("campaign_id", ""), body.get("reason", ""),
    )
    return result


@app.post("/lifecycle/promote")
async def promote_variant(request: Request):
    """Promote a winning A/B test variant to default."""
    body = await request.json()
    result = lifecycle.promote_variant(body.get("variant_id", ""), body.get("reason", ""))
    return result


@app.get("/lifecycle/log")
async def lifecycle_log(campaign_id: str = ""):
    """Get dissolution and promotion history."""
    return {
        "dissolutions": lifecycle.get_dissolution_log(campaign_id),
        "promotions": lifecycle.get_promotion_log(),
    }


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Supervisor API — {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
