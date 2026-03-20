"""
Omni OS Backend — Enterprise Tier 1 API Routes

Routes for:
1. Agent-to-Agent Communication
2. Campaign Genome Marketplace
3. Autonomous Revenue Closed-Loop
4. Multi-Modal Intelligence
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Optional

from auth import require_auth, require_permission

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AGENT-TO-AGENT COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════════

class SendMessageRequest(BaseModel):
    from_agent: str
    to_agent: str = "*"
    campaign_id: str
    subject: str = ""
    body: str = ""
    data: dict[str, Any] = {}
    msg_type: str = "insight"
    priority: str = "normal"


@router.post("/agent-comms/send")
async def send_agent_message(req: SendMessageRequest, user_id: str = Depends(require_auth)):
    from agent_comms import agent_comms, AgentMessage, MessageType, MessagePriority
    msg = AgentMessage(
        from_agent=req.from_agent, to_agent=req.to_agent,
        campaign_id=req.campaign_id,
        msg_type=MessageType(req.msg_type),
        priority=MessagePriority(req.priority),
        subject=req.subject, body=req.body, data=req.data,
    )
    msg_id = agent_comms.send(msg)
    return {"message_id": msg_id, "status": "sent"}


@router.get("/agent-comms/inbox/{agent_id}/{campaign_id}")
async def get_agent_inbox(agent_id: str, campaign_id: str, user_id: str = Depends(require_auth)):
    from agent_comms import agent_comms
    messages = agent_comms.check_inbox(agent_id, campaign_id, max_messages=20)
    return {
        "agent_id": agent_id,
        "messages": [
            {
                "id": m.id, "from": m.from_agent, "type": m.msg_type.value,
                "priority": m.priority.value, "subject": m.subject,
                "body": m.body[:500], "data": m.data,
                "timestamp": m.timestamp,
            }
            for m in messages
        ],
    }


@router.get("/agent-comms/conversation/{campaign_id}")
async def get_conversation(
    campaign_id: str,
    agent_a: str = "", agent_b: str = "",
    limit: int = 50,
    user_id: str = Depends(require_auth),
):
    from agent_comms import agent_comms
    return {"messages": agent_comms.get_conversation(campaign_id, agent_a, agent_b, limit)}


@router.get("/agent-comms/stats")
async def get_comms_stats(campaign_id: str = "", user_id: str = Depends(require_auth)):
    from agent_comms import agent_comms
    return agent_comms.get_stats(campaign_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CAMPAIGN GENOME MARKETPLACE
# ═══════════════════════════════════════════════════════════════════════════════

class MarketplaceOptInRequest(BaseModel):
    tenant_id: str


class MarketplaceQueryRequest(BaseModel):
    industry: str = ""
    icp_archetype: str = ""
    service_archetype: str = ""
    geography_region: str = ""
    company_size_bucket: str = ""
    min_quality_score: float = 0.3
    limit: int = 20


@router.post("/genome-marketplace/opt-in")
async def marketplace_opt_in(req: MarketplaceOptInRequest, user_id: str = Depends(require_auth)):
    from genome_marketplace import genome_marketplace
    genome_marketplace.opt_in(req.tenant_id)
    return {"status": "opted_in", "tenant_id": req.tenant_id}


@router.post("/genome-marketplace/opt-out")
async def marketplace_opt_out(req: MarketplaceOptInRequest, user_id: str = Depends(require_auth)):
    from genome_marketplace import genome_marketplace
    removed = genome_marketplace.opt_out(req.tenant_id)
    return {"status": "opted_out", "genomes_removed": removed}


@router.post("/genome-marketplace/contribute")
async def marketplace_contribute(
    tenant_id: str, campaign_id: str,
    user_id: str = Depends(require_auth),
):
    from genome_marketplace import genome_marketplace
    from genome import genome

    dna = genome.get_dna(campaign_id)
    if not dna:
        raise HTTPException(404, "Campaign DNA not found")

    genome_id = genome_marketplace.contribute(tenant_id, dna)
    if not genome_id:
        raise HTTPException(400, "Contribution failed — tenant not opted in or quality too low")

    return {"genome_id": genome_id, "status": "contributed"}


@router.post("/genome-marketplace/query")
async def marketplace_query(req: MarketplaceQueryRequest, user_id: str = Depends(require_auth)):
    from genome_marketplace import genome_marketplace, MarketplaceQuery
    q = MarketplaceQuery(
        industry=req.industry, icp_archetype=req.icp_archetype,
        service_archetype=req.service_archetype,
        geography_region=req.geography_region,
        company_size_bucket=req.company_size_bucket,
        min_quality_score=req.min_quality_score,
        limit=req.limit,
    )
    return genome_marketplace.query(q)


@router.get("/genome-marketplace/templates")
async def marketplace_templates(user_id: str = Depends(require_auth)):
    from genome_marketplace import genome_marketplace
    return {"templates": genome_marketplace.list_templates()}


@router.post("/genome-marketplace/generate-templates")
async def generate_templates(user_id: str = Depends(require_permission("settings", "update"))):
    from genome_marketplace import genome_marketplace
    templates = genome_marketplace.generate_templates()
    return {"generated": len(templates), "templates": [t.__dict__ for t in templates]}


@router.get("/genome-marketplace/stats")
async def marketplace_stats(user_id: str = Depends(require_auth)):
    from genome_marketplace import genome_marketplace
    return genome_marketplace.get_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. AUTONOMOUS REVENUE CLOSED-LOOP
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/revenue-loop/detect/{campaign_id}")
async def detect_revenue_signals(campaign_id: str, user_id: str = Depends(require_auth)):
    """Manually trigger signal detection for a campaign."""
    from revenue_loop import revenue_loop
    from sensing import sensing

    # Get current metrics
    metrics = sensing.get_metrics(campaign_id)
    if not metrics:
        return {"signals": 0, "message": "No metrics available for this campaign"}

    signals = revenue_loop.detect_signals(campaign_id, metrics)
    return {
        "signals": len(signals),
        "details": [
            {
                "id": s.id, "type": s.signal_type.value,
                "severity": s.severity.value, "description": s.description,
                "current_value": s.current_value, "threshold": s.threshold,
            }
            for s in signals
        ],
    }


@router.post("/revenue-loop/run/{campaign_id}")
async def run_revenue_loop(campaign_id: str, user_id: str = Depends(require_auth)):
    """Run full detection + recovery cycle for a campaign."""
    from revenue_loop import revenue_loop
    from sensing import sensing

    metrics = sensing.get_metrics(campaign_id)
    if not metrics:
        return {"status": "no_metrics"}

    result = await revenue_loop.run_detection_cycle(campaign_id, metrics)
    return result


@router.get("/revenue-loop/signals")
async def get_active_signals(campaign_id: str = "", user_id: str = Depends(require_auth)):
    from revenue_loop import revenue_loop
    return {"signals": revenue_loop.get_active_signals(campaign_id)}


@router.get("/revenue-loop/execution-log")
async def get_execution_log(limit: int = 20, user_id: str = Depends(require_auth)):
    from revenue_loop import revenue_loop
    return {"log": revenue_loop.get_execution_log(limit)}


@router.get("/revenue-loop/stats")
async def revenue_loop_stats(user_id: str = Depends(require_auth)):
    from revenue_loop import revenue_loop
    return revenue_loop.get_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MULTI-MODAL INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

class VisualAuditRequest(BaseModel):
    url: str
    brand_guidelines: dict | None = None


class AdCreativeRequest(BaseModel):
    headline: str
    body_text: str
    cta: str
    brand_colors: list[str] | None = None
    style: str = "professional"
    platform: str = "meta"
    agent_id: str = ""
    campaign_id: str = ""


class VideoScriptRequest(BaseModel):
    topic: str
    duration_seconds: int = 60
    platform: str = "youtube_shorts"
    tone: str = "engaging"


class DocumentAnalysisRequest(BaseModel):
    content: str
    doc_type: str = "contract"
    analysis_goals: list[str] | None = None


@router.post("/multimodal/visual-audit")
async def visual_audit(req: VisualAuditRequest, user_id: str = Depends(require_auth)):
    from multimodal import visual_verifier
    result = await visual_verifier.audit_url(req.url, req.brand_guidelines)
    return {
        "url": result.url,
        "scores": result.scores,
        "issues": result.issues,
        "suggestions": result.suggestions,
        "mobile_friendly": result.mobile_friendly,
        "load_time_ms": result.load_time_ms,
        "above_fold_cta_visible": result.above_fold_cta_visible,
        "social_proof_visible": result.social_proof_visible,
        "audited_at": result.audited_at,
    }


@router.post("/multimodal/ad-creative")
async def generate_ad_creative(req: AdCreativeRequest, user_id: str = Depends(require_auth)):
    from multimodal import creative_engine
    asset = await creative_engine.generate_ad_creative(
        headline=req.headline, body_text=req.body_text, cta=req.cta,
        brand_colors=req.brand_colors, style=req.style,
        platform=req.platform, agent_id=req.agent_id,
        campaign_id=req.campaign_id,
    )
    return {
        "asset_id": asset.asset_id,
        "url": asset.url,
        "metadata": asset.metadata,
    }


@router.post("/multimodal/video-script")
async def generate_video_script(req: VideoScriptRequest, user_id: str = Depends(require_auth)):
    from multimodal import creative_engine
    script = creative_engine.generate_video_script(
        topic=req.topic, duration_seconds=req.duration_seconds,
        platform=req.platform, tone=req.tone,
    )
    return script


@router.post("/multimodal/analyze-document")
async def analyze_document(req: DocumentAnalysisRequest, user_id: str = Depends(require_auth)):
    from multimodal import document_analyzer
    return await document_analyzer.analyze_document(
        content=req.content, doc_type=req.doc_type,
        analysis_goals=req.analysis_goals,
    )


@router.get("/multimodal/assets")
async def list_assets(
    campaign_id: str = "", agent_id: str = "",
    user_id: str = Depends(require_auth),
):
    from multimodal import creative_engine
    return {"assets": creative_engine.list_assets(campaign_id, agent_id)}


@router.get("/multimodal/capabilities")
async def multimodal_capabilities(user_id: str = Depends(require_auth)):
    from multimodal import AGENT_MODALITIES
    return {
        "agent_modalities": {
            agent: [m.value for m in modalities]
            for agent, modalities in AGENT_MODALITIES.items()
        },
    }
