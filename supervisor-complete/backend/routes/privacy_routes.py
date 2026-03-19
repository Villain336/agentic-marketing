"""PII / Privacy router endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from privacy import privacy_router

router = APIRouter(prefix="/privacy", tags=["Privacy"])


@router.post("/scrub")
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


@router.post("/restore")
async def restore_pii(request: Request):
    """Restore PII placeholders back to originals."""
    body = await request.json()
    restored = privacy_router.restore(body["text"], body.get("session_id", "default"))
    return {"restored_text": restored}


@router.post("/configure")
async def configure_privacy(request: Request):
    """Update privacy router configuration."""
    body = await request.json()
    from privacy import PrivacyConfig
    config = PrivacyConfig(**body)
    privacy_router.configure(config)
    return {"configured": True}


@router.post("/agent-allowlist")
async def set_agent_pii_allowlist(request: Request):
    """Set PII types allowed for a specific agent."""
    body = await request.json()
    privacy_router.set_agent_pii_allowlist(body["agent_id"], body.get("allowed_types", []))
    return {"agent_id": body["agent_id"], "allowed_types": body.get("allowed_types", [])}


@router.get("/stats")
async def privacy_stats():
    """Get privacy router statistics."""
    return privacy_router.get_stats()


@router.get("/audit")
async def privacy_audit(session_id: str = None):
    """Get PII detection audit log."""
    return {"audit": privacy_router.audit_log(session_id)}
