"""Billing portal endpoints — Stripe subscription management via httpx."""
from __future__ import annotations
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import settings
from auth import get_user_id
from webhook_auth import verify_stripe_signature

logger = logging.getLogger("supervisor.api.billing")

# ── Tier mapping from Stripe price/product IDs ─────────────────────────────
# Map Stripe product IDs or price IDs to internal tier names.
# Configure via environment or update this mapping when Stripe products change.
STRIPE_TIER_MAP: dict[str, str] = {
    # Override via settings if available; these are fallback defaults.
    # product_id or price_id → tier name
    "starter": "starter",
    "pro": "pro",
    "enterprise": "enterprise",
}


def _resolve_tier(subscription_data: dict) -> str:
    """Resolve internal tier name from Stripe subscription object."""
    items = subscription_data.get("items", {}).get("data", [])
    if not items:
        return "free"
    price = items[0].get("price", {})
    product_id = price.get("product", "")
    price_id = price.get("id", "")
    # Check product ID first, then price ID
    for key in (product_id, price_id):
        if key in STRIPE_TIER_MAP:
            return STRIPE_TIER_MAP[key]
    # Fallback: infer from price nickname or metadata
    nickname = (price.get("nickname") or "").lower()
    for tier in ("enterprise", "pro", "starter"):
        if tier in nickname:
            return tier
    return "pro"  # default paid tier

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
                           params: dict | None = None,
                           idempotency_key: str | None = None) -> dict:
    """Make an authenticated request to the Stripe API.

    CRITICAL-03 fix: POST/PUT requests include Idempotency-Key header
    to prevent duplicate charges on network retries.
    """
    url = f"{STRIPE_API_BASE}{path}"
    headers = _stripe_headers()

    # Add idempotency key for mutating requests (CRITICAL-03 fix)
    if method.upper() in ("POST", "PUT"):
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())
        headers["Idempotency-Key"] = idempotency_key

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers,
                                    data=data, params=params)
    if resp.status_code >= 400:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        logger.error(f"Stripe API error {resp.status_code}: {detail}")
        raise HTTPException(resp.status_code, f"Stripe error: {detail}")
    return resp.json()


async def _update_user_tier(stripe_customer_id: str, tier: str,
                            subscription_id: str) -> bool:
    """Update a user's subscription tier based on Stripe customer ID.

    Looks up the user by stripe_customer_id in the profiles table,
    then updates their tier and subscription metadata.
    Falls back to in-memory store if DB unavailable.
    """
    import db

    client = db._get_client()
    if not client:
        # In-memory fallback: store in module-level dict
        _tier_cache[stripe_customer_id] = {
            "tier": tier,
            "subscription_id": subscription_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        logger.info(f"Tier updated (in-memory): customer={stripe_customer_id} → {tier}")
        return True

    try:
        # Look up user by stripe_customer_id
        result = (client.table("user_subscriptions")
                  .upsert({
                      "stripe_customer_id": stripe_customer_id,
                      "tier": tier,
                      "subscription_id": subscription_id,
                      "status": "active" if tier != "free" else "cancelled",
                      "updated_at": datetime.utcnow().isoformat(),
                  }, on_conflict="stripe_customer_id")
                  .execute())
        logger.info(f"Tier updated (DB): customer={stripe_customer_id} → {tier}")
        return True
    except Exception as e:
        logger.error(f"Failed to update tier for {stripe_customer_id}: {e}")
        # Fallback to in-memory
        _tier_cache[stripe_customer_id] = {"tier": tier}
        return False


# In-memory tier cache (fallback when DB unavailable)
_tier_cache: dict[str, dict] = {}


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

    # Deterministic idempotency key: same user + same price = same key (CRITICAL-03 fix)
    idem_key = hashlib.sha256(
        f"checkout:{user_id}:{req.price_id}:{req.customer_id or req.customer_email}".encode()
    ).hexdigest()[:32]

    result = await _stripe_request("POST", "/checkout/sessions", data=data,
                                    idempotency_key=idem_key)

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
    customer_id = event_data.get("customer", "")

    logger.info(f"Stripe webhook received: {event_type} customer={customer_id}")

    # Handle subscription lifecycle events
    if event_type == "customer.subscription.created":
        tier = _resolve_tier(event_data)
        logger.info(
            f"Subscription created: {event_data.get('id')} "
            f"for customer {customer_id}, tier={tier}"
        )
        await _update_user_tier(customer_id, tier, event_data.get("id", ""))

    elif event_type == "customer.subscription.updated":
        status = event_data.get("status", "")
        tier = _resolve_tier(event_data)
        cancel_at_period_end = event_data.get("cancel_at_period_end", False)
        logger.info(
            f"Subscription updated: {event_data.get('id')} "
            f"status={status}, tier={tier}, cancel_at_period_end={cancel_at_period_end}"
        )
        if status == "active":
            # Upgrade/downgrade — update tier immediately
            await _update_user_tier(customer_id, tier, event_data.get("id", ""))
        elif status in ("past_due", "unpaid"):
            # Payment issues — restrict to starter tier
            logger.warning(f"Subscription {status} for customer {customer_id}, restricting to starter")
            await _update_user_tier(customer_id, "starter", event_data.get("id", ""))

    elif event_type == "customer.subscription.deleted":
        logger.info(
            f"Subscription cancelled: {event_data.get('id')} "
            f"for customer {customer_id}"
        )
        # Downgrade to free tier on cancellation
        await _update_user_tier(customer_id, "free", "")

    elif event_type == "invoice.payment_succeeded":
        logger.info(
            f"Invoice paid: {event_data.get('id')} "
            f"amount={event_data.get('amount_paid')} "
            f"customer={customer_id}"
        )

    elif event_type == "invoice.payment_failed":
        attempt_count = event_data.get("attempt_count", 0)
        next_attempt = event_data.get("next_payment_attempt")
        logger.warning(
            f"Invoice payment failed: {event_data.get('id')} "
            f"customer={customer_id}, attempt={attempt_count}, "
            f"next_attempt={'scheduled' if next_attempt else 'FINAL'}"
        )
        # After final retry (no next attempt), restrict access
        if not next_attempt:
            logger.warning(f"Final payment attempt failed for {customer_id}, restricting to starter")
            await _update_user_tier(customer_id, "starter", "")

    elif event_type == "checkout.session.completed":
        subscription_id = event_data.get("subscription", "")
        logger.info(
            f"Checkout completed: session={event_data.get('id')} "
            f"customer={customer_id}, subscription={subscription_id}"
        )
        # Tier update will be handled by subscription.created/updated event

    else:
        logger.debug(f"Unhandled Stripe event: {event_type}")

    # Persist subscription state change for audit
    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.payment_failed",
    ):
        try:
            import db
            await db.save_event({
                "id": f"billing-{event.get('id', '')}",
                "type": f"stripe.tier_change",
                "source_agent": "billing",
                "campaign_id": "",
                "data": {
                    "stripe_event_type": event_type,
                    "customer": customer_id,
                    "subscription_id": event_data.get("id", ""),
                    "status": event_data.get("status", ""),
                },
            })
        except Exception as e:
            logger.debug(f"Tier change event persistence skipped: {e}")

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
