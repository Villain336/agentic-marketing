"""Revenue share endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from revshare import attribution_engine, revshare_billing, REVSHARE_PLANS
from auth import get_user_id

router = APIRouter(prefix="/revshare", tags=["Revenue Share"])


@router.get("/plans")
async def list_revshare_plans():
    """List available revenue share plans."""
    return {"plans": {k: v.model_dump() for k, v in REVSHARE_PLANS.items()}}


@router.post("/enroll")
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


@router.post("/attribute")
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


@router.get("/campaign/{campaign_id}/attributions")
async def get_campaign_attributions(campaign_id: str):
    """Get revenue attributions for a campaign."""
    attrs = attribution_engine.get_attributions(campaign_id)
    by_agent = attribution_engine.get_agent_revenue(campaign_id)
    return {"attributions": [a.model_dump() for a in attrs], "by_agent": by_agent}


@router.post("/invoice")
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


@router.get("/dashboard/{user_id}")
async def revshare_dashboard(user_id: str):
    """Get revenue share dashboard for a user."""
    return revshare_billing.get_revenue_dashboard(user_id)
