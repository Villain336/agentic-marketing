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

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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
from ws import ws_manager
from versioning import versioner
from templates import get_template, list_templates, TEMPLATES
from ratelimit import RateLimitMiddleware
from costtracker import cost_tracker
from webhook_auth import verify_webhook
from whitelabel import tenant_manager
from revshare import attribution_engine, revshare_billing, REVSHARE_PLANS
from skillforge import skillforge
from marketplace import skillhub
from whatsapp import whatsapp
from replanner import replanner
from onprem import onprem
from privacy import privacy_router
from finetuning import training_collector, finetune_manager
from wideresearch import wide_research
from designview import design_view
import db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("supervisor.api")

app = FastAPI(title="Supervisor API", description="Autonomous Agency Platform — Backend Orchestration", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)


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
        "has_competitive_intel": bool(m.competitive_intel),
        "has_client_portal": bool(m.client_portal),
        "has_voice_receptionist": bool(m.voice_receptionist),
        "has_fullstack_dev": bool(m.fullstack_dev_output),
        "has_economist": bool(m.economist_briefing),
        "has_pr_comms": bool(m.pr_communications),
        "has_data_dashboards": bool(m.data_dashboards),
        "has_governance": bool(m.governance_brief),
        "has_product_roadmap": bool(m.product_roadmap),
        "has_partnerships": bool(m.partnerships_playbook),
        "has_fulfillment": bool(m.client_fulfillment),
        "has_agent_workspace": bool(m.agent_workspace),
        "has_treasury": bool(m.treasury_plan),
        "has_genome_intel": bool(m.genome_intel),
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

@app.get("/ws/status")
async def ws_status():
    """Get WebSocket connection stats."""
    return ws_manager.get_status()


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET — Real-time Campaign & Portfolio Feeds
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/campaign/{campaign_id}")
async def ws_campaign_feed(websocket: WebSocket, campaign_id: str):
    """Real-time feed for a specific campaign — agent status, metrics, triggers."""
    await ws_manager.connect(websocket, campaign_id)
    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            # Client can send ping or request refresh
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "refresh_scores":
                campaign = campaigns.get(campaign_id)
                if campaign:
                    scores = scorer.score_all(campaign)
                    await websocket.send_text(json.dumps({
                        "type": "score_update", "scores": {
                            k: {"score": v["score"], "grade": v["grade"]}
                            for k, v in scores.items()
                        },
                    }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, campaign_id)


@app.websocket("/ws/portfolio")
async def ws_portfolio_feed(websocket: WebSocket):
    """Real-time feed for portfolio-level events across all campaigns."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


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
            async for event in engine.run(agent=agent, memory=campaign.memory, campaign_id=campaign_id, tier=req.tier, campaign=campaign):
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

            # Snapshot memory version after agent completes
            versioner.snapshot(campaign_id, aid, _serialize_memory(campaign.memory))
            # Push live status via WebSocket
            asyncio.create_task(ws_manager.send_agent_status(
                campaign_id, aid, "complete"))

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
# CAMPAIGN TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/templates")
async def get_templates():
    """List all available campaign templates."""
    return {"templates": list_templates()}


@app.get("/templates/{template_id}")
async def get_template_detail(template_id: str):
    """Get full template configuration."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    return {"id": template_id, **template}


@app.post("/templates/{template_id}/launch")
async def launch_from_template(template_id: str, request: Request):
    """Launch a campaign from a template — skip onboarding, go straight to execution."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")

    body = await request.json()

    # Merge template defaults with user-provided business profile
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

    # Inject genome intelligence
    recs = genome.get_recommendations(campaign)
    if recs.get("has_data"):
        intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
        campaign.memory.genome_intel = "\n".join(intel_lines)

    # Determine agent sequence from template
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

            versioner.snapshot(campaign_id, aid, _serialize_memory(campaign.memory))
            yield f"data: {json.dumps({'event': 'agent_complete', 'agent_id': aid, 'memory': _serialize_memory(campaign.memory)})}\n\n"
            await asyncio.sleep(1)

        genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
        await db.save_campaign(campaign_id, campaign.user_id,
                               _serialize_memory(campaign.memory), "complete")
        yield f"data: {json.dumps({'event': 'campaign_complete', 'campaign_id': campaign_id, 'template': template_id, 'memory': _serialize_memory(campaign.memory)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Campaign-ID": campaign_id})


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK RECEIVER
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    """Universal webhook receiver for external services."""
    # Verify webhook signature
    raw_body = await request.body()
    headers = dict(request.headers)
    if not verify_webhook(source, raw_body, headers):
        logger.warning(f"Webhook signature verification failed for {source}")
        raise HTTPException(401, "Invalid webhook signature")

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
        # Push trigger to WebSocket listeners
        asyncio.create_task(ws_manager.send_trigger_fired(campaign_id, trigger))
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
    """Background task: re-run an agent after a sensing trigger fires.
    The adaptation engine automatically injects performance feedback and
    learned strategies — no need to manually append to brand_context."""
    agent = get_agent(agent_id)
    if not agent:
        logger.error(f"Sensing trigger: agent {agent_id} not found")
        return

    logger.info(f"Sensing trigger executing: re-running {agent_id} — {reason}")

    try:
        async for event in engine.run(
            agent=agent, memory=campaign.memory,
            campaign_id=campaign.id, tier=Tier.STANDARD,
            campaign=campaign, trigger_reason=reason,
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
    """Create a new approval request — notifies owner via Slack/Telegram/email."""
    body = await request.json()
    item = ApprovalItem(
        campaign_id=body.get("campaign_id", ""),
        agent_id=body.get("agent_id", ""),
        action_type=body.get("action_type", ""),
        content=body.get("content", {}),
    )
    approval_queue[item.id] = item

    # Push to WebSocket listeners
    asyncio.create_task(ws_manager.send_approval_needed(
        item.campaign_id, {"id": item.id, "agent_id": item.agent_id,
                           "action_type": item.action_type}))

    # Notify owner via available channels
    asyncio.create_task(_notify_approval_needed(item))

    # Persist to DB
    await db.save_approval(item.model_dump())

    return {"id": item.id, "status": "pending"}


async def _notify_approval_needed(item: ApprovalItem):
    """Send approval notification via Slack, Telegram, or email."""
    from tools import registry

    msg = (f"Approval needed: {item.action_type}\n"
           f"Agent: {item.agent_id}\n"
           f"Campaign: {item.campaign_id}\n"
           f"ID: {item.id}")

    # Try Slack first, then Telegram, then email
    if settings.slack_bot_token:
        try:
            await registry.execute("send_slack_message",
                {"channel": "#approvals", "message": msg}, "approval")
        except Exception:
            pass

    if settings.telegram_bot_token and settings.telegram_owner_chat_id:
        try:
            await registry.execute("send_telegram_message",
                {"message": msg}, "approval")
        except Exception:
            pass

    if settings.owner_email and settings.sendgrid_api_key:
        try:
            await registry.execute("send_email",
                {"to": settings.owner_email, "subject": f"Approval Needed: {item.action_type}",
                 "body": msg}, "approval")
        except Exception:
            pass


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


@app.get("/campaign/{campaign_id}/inference-costs")
async def get_inference_costs(campaign_id: str, agent_id: str = ""):
    """Get LLM inference costs for a campaign."""
    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")
    if agent_id:
        return cost_tracker.get_agent_cost(campaign_id, agent_id)
    return cost_tracker.get_campaign_cost(campaign_id)


@app.get("/costs")
async def global_costs():
    """Get global LLM inference cost stats."""
    return cost_tracker.get_global_stats()


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
# MEMORY VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/campaign/{campaign_id}/versions")
async def get_memory_versions(campaign_id: str, agent_id: str = "", limit: int = 50):
    """Get memory version history for a campaign."""
    return {"versions": versioner.get_history(campaign_id, agent_id, limit)}


@app.get("/campaign/{campaign_id}/versions/{version_id}")
async def get_memory_version(campaign_id: str, version_id: int):
    """Get a specific version with full snapshot."""
    result = versioner.get_version(campaign_id, version_id)
    if not result:
        raise HTTPException(404, "Version not found")
    return result


@app.get("/campaign/{campaign_id}/versions/diff/{v1}/{v2}")
async def diff_memory_versions(campaign_id: str, v1: int, v2: int):
    """Diff two memory versions."""
    return versioner.diff_versions(campaign_id, v1, v2)


@app.get("/campaign/{campaign_id}/versions/timeline/{field}")
async def field_timeline(campaign_id: str, field: str):
    """Get the change timeline for a specific memory field."""
    return {"field": field, "timeline": versioner.get_field_timeline(campaign_id, field)}


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
# WHITE-LABEL TENANT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/tenants")
async def create_tenant(request: Request):
    """Create a new white-label tenant."""
    body = await request.json()
    try:
        tenant = tenant_manager.create_tenant(
            name=body["name"],
            slug=body["slug"],
            owner_user_id=body.get("owner_user_id", get_user_id(request)),
            brand_name=body.get("brand_name", ""),
            brand_logo_url=body.get("brand_logo_url", ""),
            brand_color_primary=body.get("brand_color_primary", "#000000"),
            brand_color_accent=body.get("brand_color_accent", "#0066FF"),
            custom_domain=body.get("custom_domain", ""),
            plan=body.get("plan", "pro"),
        )
        return tenant.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/tenants")
async def list_tenants():
    """List all white-label tenants."""
    return {"tenants": tenant_manager.list_tenants()}


@app.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    """Get tenant configuration."""
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant.model_dump()


@app.patch("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, request: Request):
    """Update tenant configuration."""
    body = await request.json()
    tenant = tenant_manager.update_tenant(tenant_id, **body)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant.model_dump()


@app.get("/tenants/{tenant_id}/limits")
async def check_tenant_limits(tenant_id: str):
    """Check a tenant's usage against their plan limits."""
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Count campaigns owned by this tenant's users
    tenant_campaigns = sum(1 for c in campaigns.values()
                           if c.user_id == tenant.owner_user_id)

    return tenant_manager.check_limits(tenant, tenant_campaigns, 0)


@app.get("/tenants/by-slug/{slug}")
async def get_tenant_by_slug(slug: str):
    """Look up tenant by slug (used for custom domain routing)."""
    tenant = tenant_manager.get_tenant_by_slug(slug)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return {
        "id": tenant.id,
        "brand_name": tenant.brand_name or tenant.name,
        "brand_logo_url": tenant.brand_logo_url,
        "brand_color_primary": tenant.brand_color_primary,
        "brand_color_accent": tenant.brand_color_accent,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE SHARE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/revshare/plans")
async def list_revshare_plans():
    """List available revenue share plans."""
    return {"plans": {k: v.model_dump() for k, v in REVSHARE_PLANS.items()}}


@app.post("/revshare/enroll")
async def enroll_revshare(request: Request):
    """Enroll a user in a revenue share plan."""
    body = await request.json()
    user_id = body.get("user_id") or get_user_id(request)
    plan = body.get("plan", "growth")
    try:
        revshare_billing.set_user_plan(user_id, plan)
        return {"enrolled": True, "plan": plan, "user_id": user_id}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/revshare/attribute")
async def attribute_revenue(request: Request):
    """Attribute a revenue event to agent actions."""
    body = await request.json()
    attrs = attribution_engine.attribute_revenue(
        campaign_id=body["campaign_id"],
        revenue_event_id=body.get("event_id", ""),
        amount=body["amount"],
        currency=body.get("currency", "USD"),
        window_days=body.get("window_days", 30),
    )
    return {"attributions": [a.model_dump() for a in attrs]}


@app.get("/revshare/campaign/{campaign_id}/attributions")
async def get_campaign_attributions(campaign_id: str):
    """Get revenue attributions for a campaign."""
    attrs = attribution_engine.get_attributions(campaign_id)
    by_agent = attribution_engine.get_agent_revenue(campaign_id)
    return {"attributions": [a.model_dump() for a in attrs], "by_agent": by_agent}


@app.post("/revshare/invoice")
async def generate_revshare_invoice(request: Request):
    """Generate a revenue share invoice."""
    body = await request.json()
    try:
        invoice = revshare_billing.generate_invoice(
            user_id=body["user_id"], campaign_id=body["campaign_id"],
        )
        return invoice.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/revshare/dashboard/{user_id}")
async def revshare_dashboard(user_id: str):
    """Get revenue share dashboard for a user."""
    return revshare_billing.get_revenue_dashboard(user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SKILLFORGE — SELF-WRITING SKILLS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/skills/create")
async def create_skill(request: Request):
    """Create a new self-authored skill."""
    body = await request.json()
    try:
        skill = skillforge.create_skill(
            name=body["name"], description=body["description"],
            parameters=body.get("parameters", []),
            implementation_type=body.get("implementation_type", "api_chain"),
            implementation=body.get("implementation", {}),
            author_agent_id=body.get("agent_id", ""),
            campaign_id=body.get("campaign_id", ""),
            tags=body.get("tags", []),
        )
        return skill.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/skills/{skill_id}/validate")
async def validate_skill(skill_id: str):
    """Validate a skill definition."""
    result = skillforge.validate_skill(skill_id)
    return result


@app.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, request: Request):
    """Execute a validated skill."""
    body = await request.json()
    from tools import registry
    result = await skillforge.execute_skill(
        skill_id, body.get("inputs", {}),
        tool_registry=registry, llm_router=model_router,
    )
    return result.model_dump()


@app.post("/skills/{skill_id}/register")
async def register_skill_as_tool(skill_id: str):
    """Register a validated skill as a callable tool."""
    from tools import registry
    success = skillforge.register_to_tool_registry(skill_id, registry)
    if not success:
        raise HTTPException(400, "Skill must be validated before registration")
    return {"registered": True, "skill_id": skill_id}


@app.post("/skills/{skill_id}/publish")
async def publish_skill(skill_id: str):
    """Publish a skill to the marketplace."""
    success = skillforge.publish_skill(skill_id)
    if not success:
        raise HTTPException(400, "Skill must be validated before publishing")
    return {"published": True}


@app.get("/skills")
async def list_skills(campaign_id: str = None):
    """List skills for a campaign or all skills."""
    skills = skillforge.list_skills(campaign_id=campaign_id)
    return {"skills": [s.model_dump() for s in skills]}


# ═══════════════════════════════════════════════════════════════════════════════
# SKILLHUB MARKETPLACE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/marketplace/search")
async def marketplace_search(query: str = "", category: str = "",
                              item_type: str = "", sort_by: str = "installs",
                              limit: int = 20, offset: int = 0):
    """Search the SkillHub marketplace."""
    return skillhub.search(query=query, category=category, item_type=item_type,
                           sort_by=sort_by, limit=limit, offset=offset)


@app.get("/marketplace/featured")
async def marketplace_featured():
    """Get featured marketplace items."""
    return {"featured": [f.model_dump() for f in skillhub.get_featured()]}


@app.get("/marketplace/categories")
async def marketplace_categories():
    """Get marketplace category summary."""
    return {"categories": skillhub.get_categories_summary()}


@app.post("/marketplace/publish")
async def marketplace_publish(request: Request):
    """Publish an item to the marketplace."""
    body = await request.json()
    from marketplace import MarketplaceListing
    listing = MarketplaceListing(**body)
    result = skillhub.publish(listing)
    return result.model_dump()


@app.post("/marketplace/{listing_id}/install")
async def marketplace_install(listing_id: str, request: Request):
    """Install a marketplace item."""
    body = await request.json()
    item = skillhub.install(listing_id, body.get("user_id", ""), body.get("campaign_id", ""))
    if not item:
        raise HTTPException(404, "Listing not found")
    return {"installed": True, "listing_id": listing_id}


@app.post("/marketplace/{listing_id}/review")
async def marketplace_review(listing_id: str, request: Request):
    """Add a review to a marketplace listing."""
    body = await request.json()
    review = skillhub.add_review(listing_id, body.get("user_id", ""),
                                  body.get("rating", 5), body.get("comment", ""))
    if not review:
        raise HTTPException(404, "Listing not found")
    return review.model_dump()


@app.get("/marketplace/{listing_id}")
async def marketplace_get_listing(listing_id: str):
    """Get a marketplace listing."""
    listing = skillhub.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    reviews = skillhub.get_reviews(listing_id)
    return {**listing.model_dump(), "reviews": [r.model_dump() for r in reviews]}


@app.get("/marketplace/creator/{user_id}/earnings")
async def marketplace_creator_earnings(user_id: str):
    """Get creator earnings from marketplace."""
    return skillhub.get_creator_earnings(user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification (GET challenge)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == whatsapp.verify_token:
        return int(challenge)
    raise HTTPException(403, "Verification failed")


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive inbound WhatsApp messages and delivery receipts."""
    body = await request.json()
    messages = whatsapp.parse_webhook(body)
    for msg in messages:
        response = await whatsapp.process_inbound(msg)
        if response:
            await whatsapp.send_text(msg.phone, response)
    return {"status": "ok"}


@app.post("/whatsapp/send")
async def whatsapp_send(request: Request):
    """Send a WhatsApp message."""
    body = await request.json()
    msg_type = body.get("type", "text")
    if msg_type == "text":
        result = await whatsapp.send_text(body["phone"], body["text"])
    elif msg_type == "template":
        result = await whatsapp.send_template(body["phone"], body["template"],
                                               parameters=body.get("parameters"))
    elif msg_type == "buttons":
        result = await whatsapp.send_interactive_buttons(body["phone"], body["text"],
                                                          body.get("buttons", []))
    elif msg_type == "media":
        result = await whatsapp.send_media(body["phone"], body.get("media_type", "image"),
                                            body["media_url"], body.get("caption", ""))
    else:
        raise HTTPException(400, f"Unknown message type: {msg_type}")
    return result


@app.post("/whatsapp/briefing")
async def whatsapp_send_briefing(request: Request):
    """Send a daily briefing via WhatsApp."""
    body = await request.json()
    result = await whatsapp.send_daily_briefing(body["phone"], body.get("briefing", {}))
    return result


@app.post("/whatsapp/approval")
async def whatsapp_send_approval(request: Request):
    """Send an approval request via WhatsApp."""
    body = await request.json()
    result = await whatsapp.send_approval_request(body["phone"], body.get("approval", {}))
    return result


@app.get("/whatsapp/conversation/{phone}")
async def whatsapp_conversation(phone: str, limit: int = 50):
    """Get WhatsApp conversation history."""
    return {"messages": whatsapp.get_conversation(phone, limit)}


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC RE-PLANNING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/replanner/stats")
async def replanner_stats():
    """Get re-planning statistics."""
    return replanner.get_stats()


@app.get("/replanner/history/{campaign_id}/{agent_id}")
async def replanner_history(campaign_id: str, agent_id: str):
    """Get re-planning history for an agent run."""
    history = replanner.get_history(agent_id, campaign_id)
    if not history:
        return {"agent_id": agent_id, "campaign_id": campaign_id, "replans": 0}
    return history.model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
# ON-PREM / LOCAL DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/deployment/status")
async def deployment_status():
    """Get current deployment mode and configuration."""
    return onprem.health_check()


@app.post("/deployment/configure")
async def configure_deployment(request: Request):
    """Update deployment mode (cloud/hybrid/onprem/airgap)."""
    body = await request.json()
    mode = onprem.configure_mode(body.pop("mode", "cloud"), **body)
    return mode.model_dump()


@app.post("/deployment/local-llm")
async def register_local_llm(request: Request):
    """Register a local LLM endpoint."""
    body = await request.json()
    from onprem import LocalLLMConfig
    config = LocalLLMConfig(**body)
    result = onprem.register_local_llm(config)
    return result.model_dump()


@app.post("/deployment/local-llm/preset/{preset_name}")
async def register_llm_preset(preset_name: str):
    """Register a pre-configured local LLM (ollama_llama3, ollama_mixtral, etc.)."""
    result = onprem.register_preset(preset_name)
    if not result:
        raise HTTPException(404, f"Preset not found: {preset_name}")
    return result.model_dump()


@app.get("/deployment/local-llms")
async def list_local_llms():
    """List registered local LLMs."""
    return {"llms": [l.model_dump() for l in onprem.get_local_llms()]}


@app.get("/deployment/blocked-tools")
async def get_blocked_tools():
    """Get tools blocked by current deployment mode."""
    return {"blocked": onprem.get_blocked_tools(), "mode": onprem.deployment_mode.mode}


@app.post("/deployment/retention")
async def set_retention_policy(request: Request):
    """Set data retention policy."""
    body = await request.json()
    from onprem import DataRetentionPolicy
    policy = DataRetentionPolicy(**body)
    onprem.set_retention_policy(policy)
    return policy.model_dump()


@app.get("/deployment/export")
async def export_deployment_config():
    """Export on-prem configuration for backup."""
    return onprem.export_config()


# ═══════════════════════════════════════════════════════════════════════════════
# PII / PRIVACY ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/privacy/scrub")
async def scrub_pii(request: Request):
    """Scrub PII from text."""
    body = await request.json()
    result = privacy_router.scrub(
        body["text"], session_id=body.get("session_id", "default"),
        agent_id=body.get("agent_id", ""),
    )
    return {
        "scrubbed_text": result.scrubbed_text,
        "pii_count": result.pii_count,
        "has_critical": result.has_critical,
        "detections": [d.model_dump() for d in result.detections],
    }


@app.post("/privacy/restore")
async def restore_pii(request: Request):
    """Restore PII placeholders back to originals."""
    body = await request.json()
    restored = privacy_router.restore(body["text"], body.get("session_id", "default"))
    return {"restored_text": restored}


@app.post("/privacy/configure")
async def configure_privacy(request: Request):
    """Update privacy router configuration."""
    body = await request.json()
    from privacy import PrivacyConfig
    config = PrivacyConfig(**body)
    privacy_router.configure(config)
    return {"configured": True}


@app.post("/privacy/agent-allowlist")
async def set_agent_pii_allowlist(request: Request):
    """Set PII types allowed for a specific agent."""
    body = await request.json()
    privacy_router.set_agent_pii_allowlist(body["agent_id"], body.get("allowed_types", []))
    return {"agent_id": body["agent_id"], "allowed_types": body.get("allowed_types", [])}


@app.get("/privacy/stats")
async def privacy_stats():
    """Get privacy router statistics."""
    return privacy_router.get_stats()


@app.get("/privacy/audit")
async def privacy_audit(session_id: str = None):
    """Get PII detection audit log."""
    return {"audit": privacy_router.audit_log(session_id)}


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM MODEL FINE-TUNING
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/finetuning/dataset")
async def create_training_dataset(request: Request):
    """Create a training dataset from agent execution traces."""
    body = await request.json()
    ds = training_collector.create_dataset(
        user_id=body.get("user_id", ""),
        name=body["name"],
        agent_ids=body.get("agent_ids", []),
        min_score=body.get("min_score", 0.7),
        description=body.get("description", ""),
    )
    return ds.model_dump()


@app.post("/finetuning/dataset/{dataset_id}/build")
async def build_training_dataset(dataset_id: str, request: Request):
    """Build dataset from captured traces across campaigns."""
    body = await request.json()
    try:
        ds = training_collector.build_dataset(dataset_id, body.get("campaign_ids", []))
        return ds.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/finetuning/datasets")
async def list_training_datasets(user_id: str = None):
    """List training datasets."""
    datasets = training_collector.list_datasets(user_id)
    return {"datasets": [d.model_dump() for d in datasets]}


@app.post("/finetuning/job")
async def create_finetune_job(request: Request):
    """Create a fine-tuning job."""
    body = await request.json()
    try:
        job = finetune_manager.create_job(
            user_id=body.get("user_id", ""),
            dataset_id=body["dataset_id"],
            provider=body.get("provider", "openai"),
            base_model=body.get("base_model", ""),
            hyperparameters=body.get("hyperparameters"),
        )
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/finetuning/job/{job_id}/submit")
async def submit_finetune_job(job_id: str):
    """Submit a fine-tuning job to the provider."""
    try:
        job = finetune_manager.submit_job(job_id)
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/finetuning/jobs")
async def list_finetune_jobs(user_id: str = None):
    """List fine-tuning jobs."""
    jobs = finetune_manager.list_jobs(user_id)
    return {"jobs": [j.model_dump() for j in jobs]}


@app.get("/finetuning/models/{user_id}")
async def list_customer_models(user_id: str):
    """List a customer's fine-tuned models."""
    models = finetune_manager.list_customer_models(user_id)
    return {"models": [m.model_dump() for m in models]}


# ═══════════════════════════════════════════════════════════════════════════════
# WIDE RESEARCH
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/research/wide")
async def create_wide_research(request: Request):
    """Create a wide research job with parallel sub-agents."""
    body = await request.json()
    job = wide_research.create_job(
        topic=body["topic"],
        campaign_id=body.get("campaign_id", ""),
        user_id=body.get("user_id", ""),
        strategy=body.get("strategy", "general"),
        max_parallel=body.get("max_parallel", 5),
        custom_queries=body.get("custom_queries"),
        targets=body.get("targets"),
    )
    return job.model_dump()


@app.post("/research/wide/{job_id}/execute")
async def execute_wide_research(job_id: str):
    """Execute a wide research job."""
    from tools import registry
    try:
        job = await wide_research.execute(job_id, llm_router=model_router, tool_registry=registry)
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/research/wide/{job_id}")
async def get_wide_research(job_id: str):
    """Get wide research job status and results."""
    job = wide_research.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    synthesis = wide_research.get_synthesis(job_id)
    result = job.model_dump()
    if synthesis:
        result["synthesis"] = synthesis.model_dump()
    return result


@app.get("/research/wide")
async def list_wide_research(campaign_id: str = None, user_id: str = None):
    """List wide research jobs."""
    jobs = wide_research.list_jobs(campaign_id, user_id)
    return {"jobs": [j.model_dump() for j in jobs]}


@app.get("/research/strategies")
async def list_research_strategies():
    """List available research decomposition strategies."""
    return {"strategies": wide_research.get_available_strategies()}


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN VIEW
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/design/canvas")
async def create_design_canvas(request: Request):
    """Create a new design canvas."""
    body = await request.json()
    canvas = design_view.create_canvas(
        campaign_id=body["campaign_id"],
        name=body.get("name", "Untitled"),
        template_id=body.get("template_id", ""),
        width=body.get("width", 1440),
        height=body.get("height", 900),
    )
    return canvas.model_dump()


@app.get("/design/canvas/{canvas_id}")
async def get_design_canvas(canvas_id: str):
    """Get a design canvas."""
    canvas = design_view.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(404, "Canvas not found")
    return canvas.model_dump()


@app.get("/design/canvases/{campaign_id}")
async def list_design_canvases(campaign_id: str):
    """List canvases for a campaign."""
    canvases = design_view.list_canvases(campaign_id)
    return {"canvases": [c.model_dump() for c in canvases]}


@app.post("/design/canvas/{canvas_id}/component")
async def add_design_component(canvas_id: str, request: Request):
    """Add a component from the library to a canvas."""
    body = await request.json()
    element = design_view.add_component(
        canvas_id, body["component"],
        x=body.get("x", 0), y=body.get("y", 0),
        overrides=body.get("overrides"),
    )
    if not element:
        raise HTTPException(400, "Canvas or component not found")
    return element.model_dump()


@app.patch("/design/canvas/{canvas_id}/element/{element_id}")
async def update_design_element(canvas_id: str, element_id: str, request: Request):
    """Update a design element's properties or styles."""
    body = await request.json()
    element = design_view.update_element(canvas_id, element_id, body)
    if not element:
        raise HTTPException(404, "Canvas or element not found")
    return element.model_dump()


@app.delete("/design/canvas/{canvas_id}/element/{element_id}")
async def delete_design_element(canvas_id: str, element_id: str):
    """Delete a design element."""
    success = design_view.delete_element(canvas_id, element_id)
    if not success:
        raise HTTPException(404, "Canvas not found")
    return {"deleted": True}


@app.get("/design/canvas/{canvas_id}/export/html")
async def export_design_html(canvas_id: str, responsive: bool = True):
    """Export canvas as production HTML."""
    html = design_view.export_html(canvas_id, responsive)
    if not html:
        raise HTTPException(404, "Canvas not found")
    return {"html": html}


@app.get("/design/canvas/{canvas_id}/export/react")
async def export_design_react(canvas_id: str):
    """Export canvas as a React component."""
    react = design_view.export_react(canvas_id)
    if not react:
        raise HTTPException(404, "Canvas not found")
    return {"react": react}


@app.get("/design/templates")
async def list_design_templates(category: str = ""):
    """List available design templates."""
    templates = design_view.get_templates(category)
    return {"templates": [t.model_dump() for t in templates]}


@app.get("/design/components")
async def list_design_components():
    """List the component library."""
    return {"components": design_view.get_component_library()}


@app.get("/design/canvas/{canvas_id}/history")
async def get_design_history(canvas_id: str):
    """Get edit history for undo/redo."""
    return {"history": design_view.get_edit_history(canvas_id)}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTER USE — Live Browser Streaming, Multi-Browser, Recordings, Handoff
# ═══════════════════════════════════════════════════════════════════════════════

from computer_use import browser_pool


@app.post("/browser/sessions")
async def create_browser_session(payload: dict):
    """Launch a live browser session for an agent with real-time streaming."""
    session = await browser_pool.create_session(
        agent_id=payload.get("agent_id", ""),
        campaign_id=payload.get("campaign_id", ""),
        start_url=payload.get("start_url", ""),
        viewport=payload.get("viewport"),
        proxy=payload.get("proxy", ""),
        recording=payload.get("recording", True),
    )
    return session.to_dict()


@app.get("/browser/sessions")
async def list_browser_sessions(campaign_id: str = "", agent_id: str = "", status: str = ""):
    """List browser sessions with optional filters."""
    return {"sessions": browser_pool.list_sessions(campaign_id, agent_id, status)}


@app.get("/browser/sessions/{session_id}")
async def get_browser_session(session_id: str):
    """Get details of a specific browser session."""
    session = browser_pool.get_session(session_id)
    if not session:
        raise HTTPException(404, "Browser session not found")
    return session


@app.post("/browser/sessions/{session_id}/action")
async def execute_browser_action(session_id: str, payload: dict):
    """Execute a browser action (click, type, navigate, etc.) in a live session."""
    from computer_use import BrowserAction, ActionType
    coords = None
    if payload.get("coordinates"):
        coords = tuple(payload["coordinates"])
    action = BrowserAction(
        action_type=ActionType(payload["action_type"]),
        selector=payload.get("selector", ""),
        value=payload.get("value", ""),
        coordinates=coords,
        description=payload.get("description", ""),
    )
    result = await browser_pool.execute_action(session_id, action)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/vision-step")
async def vision_navigate_step(session_id: str, payload: dict):
    """Execute one vision-guided navigation step: screenshot → vision model → action."""
    result = await browser_pool.vision_step(
        session_id, payload["goal"], payload.get("screenshot_b64", "")
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/vision-plan")
async def vision_plan_steps(session_id: str, payload: dict):
    """Plan a full multi-step browser interaction using vision analysis."""
    session = browser_pool._sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Browser session not found")
    plan = await browser_pool._vision.plan_multi_step(
        payload.get("screenshot_b64", ""), payload["goal"], payload.get("max_steps", 20)
    )
    return {"session_id": session_id, "plan": plan}


@app.post("/browser/parallel")
async def launch_parallel_browsers(payload: dict):
    """Launch multiple browser sessions simultaneously — N agents, N browsers."""
    result = await browser_pool.run_parallel_sessions(payload["tasks"])
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/handoff")
async def request_human_handoff(session_id: str, payload: dict):
    """Agent yields browser control to human. Sends notification with live stream link."""
    result = await browser_pool.request_human_handoff(
        session_id, payload["reason"], payload.get("notify_channels")
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/takeover")
async def human_takeover(session_id: str, payload: dict):
    """Human assumes direct browser control during a live session."""
    result = await browser_pool.human_takeover(session_id, payload.get("user_id", "anonymous"))
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/release")
async def human_release(session_id: str):
    """Human returns browser control to agent."""
    result = await browser_pool.human_release(session_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/human-action")
async def human_browser_action(session_id: str, payload: dict):
    """Execute a human-initiated browser action during takeover mode."""
    result = await browser_pool.human_action(
        session_id, payload["action_type"],
        payload.get("selector", ""), payload.get("value", ""),
        tuple(payload["coordinates"]) if payload.get("coordinates") else None,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/browser/sessions/{session_id}/close")
async def close_browser_session(session_id: str):
    """Close a browser session and finalize its recording."""
    result = await browser_pool.close_session(session_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/browser/dashboard")
async def browser_dashboard():
    """Multi-browser control panel — all active sessions, streams, and stats."""
    return browser_pool.get_dashboard()


@app.get("/browser/stats")
async def browser_stats():
    """Aggregate statistics across all browser sessions."""
    return browser_pool.get_stats()


@app.get("/browser/recordings")
async def list_recordings(campaign_id: str = "", agent_id: str = ""):
    """List all browser session recordings."""
    return {"recordings": browser_pool.list_recordings(campaign_id, agent_id)}


@app.get("/browser/recordings/{recording_id}")
async def get_recording(recording_id: str, format: str = "json"):
    """Get or export a browser session recording."""
    result = await browser_pool.export_recording(recording_id, format)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/browser/recordings/{recording_id}/annotate")
async def annotate_recording(recording_id: str, payload: dict):
    """Add human annotation to a specific frame in a recording."""
    result = await browser_pool.annotate_recording(
        recording_id, payload["frame_index"], payload["annotation"], payload.get("author", "user")
    )
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.websocket("/ws/browser/{session_id}/stream")
async def browser_stream_ws(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for live browser session streaming.

    Viewers connect here to watch an agent's browser in real-time.
    All browser actions, vision analyses, and state changes are streamed.
    During human takeover, this same connection receives human actions too.
    """
    await websocket.accept()
    await browser_pool.subscribe_to_stream(session_id, websocket)

    session = browser_pool.get_session(session_id)
    if session:
        await websocket.send_json({
            "type": "session_state",
            "session": session,
            "message": "Connected to live browser stream. You will see all agent actions in real-time.",
        })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "human_action":
                s = browser_pool._sessions.get(session_id)
                if s and s.human_control:
                    await browser_pool.human_action(
                        session_id, msg["action_type"],
                        msg.get("selector", ""), msg.get("value", ""),
                        tuple(msg["coordinates"]) if msg.get("coordinates") else None,
                    )
    except WebSocketDisconnect:
        await browser_pool.unsubscribe_from_stream(session_id, websocket)


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Supervisor API — {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
