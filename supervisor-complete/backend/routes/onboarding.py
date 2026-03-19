"""Onboarding CRUD, vision interview, crawl URL, search references, visual DNA, market research."""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from models import (
    AgentStreamEvent, BusinessProfile, CampaignMemory, StepType, Tier,
)
from providers import router as model_router
from engine import engine
from agents import get_agent
from auth import get_user_id, validate_id
from store import store
import db

logger = logging.getLogger("supervisor.api.onboarding")

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.post("/create")
async def create_onboarding(request: Request):
    """Create a new onboarding profile."""
    from models import OnboardingProfile
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    profile = OnboardingProfile(user_id=user_id)
    store.put_onboarding(user_id, profile)

    await db.save_onboarding_profile(profile.model_dump())

    return {"id": profile.id, "current_stage": profile.current_stage}


@router.get("/{profile_id}")
async def get_onboarding(profile_id: str, request: Request):
    """Get onboarding profile state."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(profile_id, "profile_id")
    profile = store.get_onboarding(user_id, profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")
    return profile.model_dump()


@router.post("/{profile_id}/stage/{stage}")
async def update_onboarding_stage(profile_id: str, stage: int, request: Request):
    """Update a specific onboarding stage with data."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(profile_id, "profile_id")
    profile = store.get_onboarding(user_id, profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    body = await request.json()

    if stage == 1:
        from models import BusinessBrief
        profile.business_brief = BusinessBrief(**body.get("business_brief", {}))
    elif stage == 2:
        from models import VisualDNA
        profile.visual_dna = VisualDNA(**body.get("visual_dna", {}))
        profile.mood_board_references = body.get("reference_urls", [])
    elif stage == 3:
        from models import FormationProfile
        profile.formation = FormationProfile(**body.get("formation", {}))
    elif stage == 4:
        from models import RevenueModel
        profile.revenue_model = RevenueModel(**body.get("revenue_model", {}))
    elif stage == 5:
        profile.channels = body.get("channels", {})
    elif stage == 6:
        profile.market_research = body.get("market_research", {})
    elif stage == 7:
        from models import AutonomyConfig
        profile.autonomy = AutonomyConfig(**body.get("autonomy", {}))

    if stage not in profile.completed_stages:
        profile.completed_stages.append(stage)
    profile.current_stage = min(stage + 1, 7)

    return {"updated": True, "current_stage": profile.current_stage,
            "completed_stages": profile.completed_stages}


@router.post("/{profile_id}/vision-interview")
async def run_vision_interview(profile_id: str, request: Request):
    """Run the Vision Interview agent for Stage 1 onboarding -- SSE stream."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(profile_id, "profile_id")
    profile = store.get_onboarding(user_id, profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    body = await request.json()
    user_message = body.get("message", "")
    agent = get_agent("vision_interview")
    if not agent:
        raise HTTPException(500, "Vision Interview agent not configured")

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


def _validate_url(url: str) -> str:
    """Validate and sanitize a URL to prevent SSRF attacks."""
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(400, "Invalid URL")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only HTTP/HTTPS URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, "No hostname in URL")

    # Block private/reserved IPs
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise HTTPException(400, "Internal/private IP addresses are not allowed")
    except ValueError:
        # hostname is a domain name, resolve it
        import socket
        try:
            resolved = socket.getaddrinfo(hostname, None)
            for _, _, _, _, addr in resolved:
                ip = ipaddress.ip_address(addr[0])
                if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                    raise HTTPException(400, "URL resolves to a private/internal IP address")
        except socket.gaierror:
            raise HTTPException(400, f"Cannot resolve hostname: {hostname}")

    # Block common internal hostnames
    blocked = {"localhost", "metadata.google.internal", "169.254.169.254"}
    if hostname.lower() in blocked:
        raise HTTPException(400, "Blocked hostname")

    return url


@router.post("/crawl-url")
async def crawl_url(request: Request):
    """Crawl a URL and extract visual signals for mood board (Stage 2)."""
    body = await request.json()
    url = body.get("url", "")
    if not url:
        raise HTTPException(400, "No URL provided")

    url = _validate_url(url)

    from tools import registry
    scrape_result = await registry.execute("web_scrape", {"url": url, "max_chars": 5000}, "crawl")

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


@router.post("/search-references")
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


@router.post("/generate-visual-dna")
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


@router.post("/{profile_id}/market-research")
async def run_market_research(profile_id: str, request: Request):
    """Run market research agents during onboarding (Stage 6) -- SSE stream."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(profile_id, "profile_id")
    profile = store.get_onboarding(user_id, profile_id)
    if not profile:
        raise HTTPException(404, "Onboarding profile not found")

    biz = BusinessProfile(
        name=profile.business_brief.name or "Agency",
        service=profile.business_brief.service_definition or "",
        icp=profile.business_brief.icp_firmographic or "",
        geography="", goal="",
    )
    memory = CampaignMemory(business=biz)

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
