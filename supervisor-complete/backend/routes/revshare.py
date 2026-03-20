"""Revenue share endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from revshare import attribution_engine, revshare_billing, REVSHARE_PLANS
from auth import get_user_id, validate_campaign_id
from store import store

router = APIRouter(prefix="/revshare", tags=["Revenue Share"])


@router.get("/plans")
async def list_revshare_plans():
    """List available revenue share plans (public)."""
    return {"plans": {k: v.model_dump() for k, v in REVSHARE_PLANS.items()}}


@router.post("/enroll")
async def enroll_revshare(request: Request):
    """Enroll the authenticated user in a revenue share plan."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    plan = body.get("plan", "growth")
    try:
        revshare_billing.set_user_plan(user_id, plan)
        return {"enrolled": True, "plan": plan, "user_id": user_id}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/attribute")
async def attribute_revenue(request: Request):
    """Attribute a revenue event to agent actions."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    campaign_id = body["campaign_id"]
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    attrs = attribution_engine.attribute_revenue(
        campaign_id=campaign_id,
        revenue_event_id=body.get("event_id", ""),
        amount=body["amount"],
        currency=body.get("currency", "USD"),
        window_days=body.get("window_days", 30),
    )
    return {"attributions": [a.model_dump() for a in attrs]}


@router.get("/campaign/{campaign_id}/attributions")
async def get_campaign_attributions(campaign_id: str, request: Request):
    """Get revenue attributions for a campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    if not store.get_campaign(user_id, campaign_id):
        raise HTTPException(404, "Campaign not found")
    attrs = attribution_engine.get_attributions(campaign_id)
    by_agent = attribution_engine.get_agent_revenue(campaign_id)
    return {"attributions": [a.model_dump() for a in attrs], "by_agent": by_agent}


@router.post("/invoice")
async def generate_revshare_invoice(request: Request):
    """Generate a revenue share invoice for the authenticated user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    try:
        invoice = revshare_billing.generate_invoice(
            user_id=user_id, campaign_id=body["campaign_id"],
        )
        return invoice.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/dashboard")
async def revshare_dashboard(request: Request):
    """Get revenue share dashboard for the authenticated user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return revshare_billing.get_revenue_dashboard(user_id)
