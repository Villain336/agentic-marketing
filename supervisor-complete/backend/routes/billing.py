"""Billing portal endpoints — Stripe subscription management via httpx."""
from __future__ import annotations
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import settings
from auth import get_user_id
from webhook_auth import verify_stripe_signature

logger = logging.getLogger("supervisor.api.billing")

router = APIRouter(tags=["Billing"])

STRIPE_API_BASE = "https://api.stripe.com/v1"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _stripe_headers() -> dict:
    """Return authorization headers for Stripe API calls."""
    if not settings.stripe_api_key:
        raise HTTPException(503, "Stripe API key not configured")
    return {
        "Authorization": f"Bearer {settings.stripe_api_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def _stripe_request(method: str, path: str, data: dict | None = None,
                           params: dict | None = None) -> dict:
    """Make an authenticated request to the Stripe API."""
    url = f"{STRIPE_API_BASE}{path}"
    headers = _stripe_headers()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers,
                                    data=data, params=params)
    if resp.status_code >= 400:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        logger.error(f"Stripe API error {resp.status_code}: {detail}")
        raise HTTPException(resp.status_code, f"Stripe error: {detail}")
    return resp.json()


# ── Request Models ───────────────────────────────────────────────────────────

class CreatePortalSessionRequest(BaseModel):
    customer_id: str
    return_url: str = "http://localhost:3000/settings/billing"


class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    success_url: str = "http://localhost:3000/settings/billing?session_id={CHECKOUT_SESSION_ID}"
    cancel_url: str = "http://localhost:3000/settings/billing"


class SubscriptionQueryRequest(BaseModel):
    customer_id: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/billing/create-portal-session")
async def create_portal_session(req: CreatePortalSessionRequest, request: Request):
    """Create a Stripe Customer Portal session for managing subscriptions,
    invoices, and payment methods."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    result = await _stripe_request("POST", "/billing_portal/sessions", data={
        "customer": req.customer_id,
        "return_url": req.return_url,
    })

    return {"url": result.get("url"), "id": result.get("id")}


@router.get("/billing/subscription")
async def get_subscription(request: Request, customer_id: str = ""):
    """Get current subscription status for a Stripe customer."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    if not customer_id:
        raise HTTPException(400, "customer_id query parameter is required")

    result = await _stripe_request("GET", "/subscriptions", params={
        "customer": customer_id,
        "status": "all",
        "limit": "1",
    })

    subscriptions = result.get("data", [])
    if not subscriptions:
        return {"status": "none", "subscription": None}

    sub = subscriptions[0]
    return {
        "status": sub.get("status"),
        "subscription": {
            "id": sub.get("id"),
            "status": sub.get("status"),
            "current_period_start": sub.get("current_period_start"),
            "current_period_end": sub.get("current_period_end"),
            "cancel_at_period_end": sub.get("cancel_at_period_end"),
            "plan": {
                "id": sub.get("plan", {}).get("id"),
                "amount": sub.get("plan", {}).get("amount"),
                "currency": sub.get("plan", {}).get("currency"),
                "interval": sub.get("plan", {}).get("interval"),
                "product": sub.get("plan", {}).get("product"),
            } if sub.get("plan") else None,
            "items": [
                {
                    "id": item.get("id"),
                    "price_id": item.get("price", {}).get("id"),
                    "quantity": item.get("quantity"),
                }
                for item in sub.get("items", {}).get("data", [])
            ],
        },
    }


@router.post("/billing/create-checkout-session")
async def create_checkout_session(req: CreateCheckoutSessionRequest,
                                  request: Request):
    """Create a Stripe Checkout session for subscribing to a tier."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    data = {
        "mode": "subscription",
        "line_items[0][price]": req.price_id,
        "line_items[0][quantity]": "1",
        "success_url": req.success_url,
        "cancel_url": req.cancel_url,
    }

    if req.customer_id:
        data["customer"] = req.customer_id
    elif req.customer_email:
        data["customer_email"] = req.customer_email

    result = await _stripe_request("POST", "/checkout/sessions", data=data)

    return {
        "session_id": result.get("id"),
        "url": result.get("url"),
    }


@router.get("/billing/invoices")
async def list_invoices(request: Request, customer_id: str = "",
                        limit: int = 10):
    """List recent invoices for a Stripe customer."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    if not customer_id:
        raise HTTPException(400, "customer_id query parameter is required")

    limit = max(1, min(limit, 100))

    result = await _stripe_request("GET", "/invoices", params={
        "customer": customer_id,
        "limit": str(limit),
    })

    invoices = [
        {
            "id": inv.get("id"),
            "number": inv.get("number"),
            "status": inv.get("status"),
            "amount_due": inv.get("amount_due"),
            "amount_paid": inv.get("amount_paid"),
            "currency": inv.get("currency"),
            "created": inv.get("created"),
            "period_start": inv.get("period_start"),
            "period_end": inv.get("period_end"),
            "hosted_invoice_url": inv.get("hosted_invoice_url"),
            "invoice_pdf": inv.get("invoice_pdf"),
        }
        for inv in result.get("data", [])
    ]

    return {"invoices": invoices, "count": len(invoices)}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscription lifecycle.

    Signature verification is performed via webhook_auth.verify_stripe_signature.
    This endpoint is meant to be registered as a public webhook path so the
    auth middleware will not require a JWT.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    if not verify_stripe_signature(payload, signature):
        raise HTTPException(400, "Invalid Stripe webhook signature")

    try:
        import json
        event = json.loads(payload)
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook received: {event_type}")

    # Handle subscription lifecycle events
    if event_type == "customer.subscription.created":
        logger.info(
            f"Subscription created: {event_data.get('id')} "
            f"for customer {event_data.get('customer')}"
        )
    elif event_type == "customer.subscription.updated":
        logger.info(
            f"Subscription updated: {event_data.get('id')} "
            f"status={event_data.get('status')}"
        )
    elif event_type == "customer.subscription.deleted":
        logger.info(
            f"Subscription cancelled: {event_data.get('id')} "
            f"for customer {event_data.get('customer')}"
        )
    elif event_type == "invoice.payment_succeeded":
        logger.info(
            f"Invoice paid: {event_data.get('id')} "
            f"amount={event_data.get('amount_paid')} "
            f"customer={event_data.get('customer')}"
        )
    elif event_type == "invoice.payment_failed":
        logger.warning(
            f"Invoice payment failed: {event_data.get('id')} "
            f"customer={event_data.get('customer')}"
        )
    elif event_type == "checkout.session.completed":
        logger.info(
            f"Checkout completed: session={event_data.get('id')} "
            f"customer={event_data.get('customer')}"
        )
    else:
        logger.debug(f"Unhandled Stripe event: {event_type}")

    # Persist event for audit
    try:
        import db
        await db.save_event({
            "id": event.get("id", ""),
            "type": f"stripe.{event_type}",
            "source_agent": "billing",
            "campaign_id": "",
            "data": {"stripe_event_type": event_type,
                     "object_id": event_data.get("id", ""),
                     "customer": event_data.get("customer", "")},
        })
    except Exception as e:
        logger.debug(f"Webhook event persistence skipped: {e}")

    return {"received": True}
