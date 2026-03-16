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
from agents import AGENTS, AGENT_MAP, AGENT_ORDER, BACKOFFICE_LAYER, get_agent
from scoring import scorer
from sensing import sensing
from wallet import wallet
from gauntlet import gauntlet

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("supervisor.api")

app = FastAPI(title="Supervisor API", description="Autonomous Agency Platform — Backend Orchestration", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
                continue

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

    trigger = await sensing.process_event(campaign, event)

    result = {"received": True, "processed": True, "source": source}
    if trigger:
        result["trigger"] = trigger
        logger.info(f"Webhook trigger: {trigger}")

    return result


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

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Supervisor API — {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
