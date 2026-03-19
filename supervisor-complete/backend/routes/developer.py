"""
Phase 2 — Developer Platform: Public REST API, API Keys, Outbound Webhooks, OAuth Provider.

This module provides the developer-facing infrastructure that transforms Omni OS
from a product into a platform:
  - Developer API key generation & management
  - Outbound webhook subscriptions (push events to external URLs)
  - OAuth 2.0 provider ("Sign in with Omni")
  - API versioning and OpenAPI metadata
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth import get_user_id, validate_id

logger = logging.getLogger("omnios.developer")

router = APIRouter(tags=["Developer Platform"])


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DEVELOPER API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

class APIKeyRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"key_{uuid4().hex[:16]}")
    user_id: str = ""
    name: str = ""
    prefix: str = ""  # First 8 chars shown to user for identification
    key_hash: str = ""  # SHA-256 hash of the full key
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    rate_limit: int = 1000  # requests per hour
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: str = ""
    expires_at: str = ""  # empty = never expires
    revoked: bool = False


class CreateAPIKeyRequest(BaseModel):
    name: str = "My API Key"
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    expires_in_days: Optional[int] = None  # None = never expires


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    rate_limit: int
    created_at: str
    last_used_at: str
    expires_at: str
    revoked: bool


# In-memory stores (swap for DB in production)
_api_keys: dict[str, APIKeyRecord] = {}  # key_id -> record
_key_hash_index: dict[str, str] = {}  # sha256(key) -> key_id
_key_usage: dict[str, list[float]] = {}  # key_id -> list of timestamps

VALID_SCOPES = {"read", "write", "agents", "campaigns", "webhooks", "admin"}


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(request: Request) -> Optional[APIKeyRecord]:
    """Verify an API key from the X-API-Key header. Returns the key record or None."""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        return None

    key_hash = _hash_key(api_key)
    key_id = _key_hash_index.get(key_hash)
    if not key_id:
        return None

    record = _api_keys.get(key_id)
    if not record or record.revoked:
        return None

    # Check expiry
    if record.expires_at:
        try:
            expires = datetime.fromisoformat(record.expires_at)
            if datetime.utcnow() > expires:
                return None
        except ValueError:
            pass

    # Rate limiting check
    now = time.time()
    window = _key_usage.get(key_id, [])
    window = [t for t in window if now - t < 3600]  # 1hr window
    if len(window) >= record.rate_limit:
        return None

    window.append(now)
    _key_usage[key_id] = window

    # Update last_used
    record.last_used_at = datetime.utcnow().isoformat()

    return record


@router.post("/developer/api-keys")
async def create_api_key(req: CreateAPIKeyRequest, request: Request):
    """Generate a new developer API key."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    # Validate scopes
    invalid = set(req.scopes) - VALID_SCOPES
    if invalid:
        raise HTTPException(400, f"Invalid scopes: {invalid}. Valid: {VALID_SCOPES}")

    # Generate key
    raw_key = f"omni_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)

    expires_at = ""
    if req.expires_in_days:
        expires_at = (datetime.utcnow() + timedelta(days=req.expires_in_days)).isoformat()

    record = APIKeyRecord(
        user_id=user_id,
        name=req.name,
        prefix=raw_key[:12],
        key_hash=key_hash,
        scopes=req.scopes,
        expires_at=expires_at,
    )

    _api_keys[record.id] = record
    _key_hash_index[key_hash] = record.id

    logger.info(f"User {user_id[:8]}... created API key {record.id}")

    # Return the raw key ONCE — it cannot be retrieved again
    return {
        "key": raw_key,
        "id": record.id,
        "name": record.name,
        "prefix": record.prefix,
        "scopes": record.scopes,
        "expires_at": record.expires_at,
        "message": "Save this key — it won't be shown again.",
    }


@router.get("/developer/api-keys")
async def list_api_keys(request: Request):
    """List all API keys for the current user (keys are masked)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    keys = [
        APIKeyResponse(
            id=k.id, name=k.name, prefix=k.prefix,
            scopes=k.scopes, rate_limit=k.rate_limit,
            created_at=k.created_at, last_used_at=k.last_used_at,
            expires_at=k.expires_at, revoked=k.revoked,
        )
        for k in _api_keys.values() if k.user_id == user_id
    ]
    return {"keys": keys}


@router.delete("/developer/api-keys/{key_id}")
async def revoke_api_key(key_id: str, request: Request):
    """Revoke an API key (cannot be undone)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(key_id, "key_id")

    record = _api_keys.get(key_id)
    if not record or record.user_id != user_id:
        raise HTTPException(404, "API key not found")

    record.revoked = True
    # Remove from hash index
    _key_hash_index.pop(record.key_hash, None)

    logger.info(f"User {user_id[:8]}... revoked API key {key_id}")
    return {"id": key_id, "status": "revoked"}


@router.get("/developer/api-keys/{key_id}/usage")
async def get_api_key_usage(key_id: str, request: Request):
    """Get usage stats for an API key."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(key_id, "key_id")

    record = _api_keys.get(key_id)
    if not record or record.user_id != user_id:
        raise HTTPException(404, "API key not found")

    now = time.time()
    window = _key_usage.get(key_id, [])
    last_hour = len([t for t in window if now - t < 3600])
    last_day = len([t for t in window if now - t < 86400])

    return {
        "key_id": key_id,
        "requests_last_hour": last_hour,
        "requests_last_24h": last_day,
        "rate_limit": record.rate_limit,
        "remaining": max(0, record.rate_limit - last_hour),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. OUTBOUND WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookSubscription(BaseModel):
    id: str = Field(default_factory=lambda: f"wh_{uuid4().hex[:12]}")
    user_id: str = ""
    url: str  # HTTPS endpoint to deliver events
    events: list[str] = Field(default_factory=lambda: ["*"])  # event types to subscribe
    secret: str = Field(default_factory=lambda: secrets.token_hex(32))
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    failure_count: int = 0
    last_delivered_at: str = ""
    last_status_code: int = 0


class CreateWebhookRequest(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["*"])


class WebhookDelivery(BaseModel):
    id: str = Field(default_factory=lambda: f"del_{uuid4().hex[:12]}")
    webhook_id: str
    event_type: str
    payload: dict
    status_code: int = 0
    response_body: str = ""
    delivered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = False


# In-memory stores
_webhooks: dict[str, WebhookSubscription] = {}  # wh_id -> subscription
_webhook_deliveries: list[WebhookDelivery] = []  # recent deliveries

VALID_WEBHOOK_EVENTS = {
    "*",
    "agent.started", "agent.completed", "agent.failed",
    "campaign.started", "campaign.completed",
    "approval.requested", "approval.decided",
    "lead.created", "lead.qualified",
    "email.sent", "email.opened", "email.replied",
    "content.published", "content.approved",
    "ad.launched", "ad.paused",
    "payment.received", "invoice.created",
}

MAX_WEBHOOKS_PER_USER = 10
MAX_DELIVERY_LOG = 500


@router.post("/developer/webhooks")
async def create_webhook(req: CreateWebhookRequest, request: Request):
    """Subscribe to outbound webhook events."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    # Validate URL
    parsed = urllib.parse.urlparse(req.url)
    if parsed.scheme != "https":
        raise HTTPException(400, "Webhook URL must use HTTPS")
    if not parsed.hostname:
        raise HTTPException(400, "Invalid webhook URL")

    # Validate events
    invalid = set(req.events) - VALID_WEBHOOK_EVENTS
    if invalid:
        raise HTTPException(400, f"Invalid events: {invalid}")

    # Limit per user
    user_hooks = [w for w in _webhooks.values() if w.user_id == user_id and not w.active is False]
    if len(user_hooks) >= MAX_WEBHOOKS_PER_USER:
        raise HTTPException(400, f"Maximum {MAX_WEBHOOKS_PER_USER} webhooks per user")

    sub = WebhookSubscription(user_id=user_id, url=req.url, events=req.events)
    _webhooks[sub.id] = sub

    logger.info(f"User {user_id[:8]}... created webhook {sub.id} -> {req.url}")

    return {
        "id": sub.id,
        "url": sub.url,
        "events": sub.events,
        "secret": sub.secret,
        "active": sub.active,
        "message": "Save the secret — it's used to verify webhook signatures.",
    }


@router.get("/developer/webhooks")
async def list_webhooks(request: Request):
    """List all webhook subscriptions for the current user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    hooks = [
        {
            "id": w.id, "url": w.url, "events": w.events,
            "active": w.active, "created_at": w.created_at,
            "failure_count": w.failure_count,
            "last_delivered_at": w.last_delivered_at,
            "last_status_code": w.last_status_code,
        }
        for w in _webhooks.values() if w.user_id == user_id
    ]
    return {"webhooks": hooks}


@router.delete("/developer/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, request: Request):
    """Delete a webhook subscription."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(webhook_id, "webhook_id")

    sub = _webhooks.get(webhook_id)
    if not sub or sub.user_id != user_id:
        raise HTTPException(404, "Webhook not found")

    del _webhooks[webhook_id]
    return {"id": webhook_id, "status": "deleted"}


@router.patch("/developer/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, request: Request):
    """Update a webhook (toggle active, change events, change URL)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(webhook_id, "webhook_id")

    sub = _webhooks.get(webhook_id)
    if not sub or sub.user_id != user_id:
        raise HTTPException(404, "Webhook not found")

    body = await request.json()
    if "active" in body:
        sub.active = bool(body["active"])
    if "events" in body:
        invalid = set(body["events"]) - VALID_WEBHOOK_EVENTS
        if invalid:
            raise HTTPException(400, f"Invalid events: {invalid}")
        sub.events = body["events"]
    if "url" in body:
        parsed = urllib.parse.urlparse(body["url"])
        if parsed.scheme != "https":
            raise HTTPException(400, "Webhook URL must use HTTPS")
        sub.url = body["url"]

    return {"id": webhook_id, "status": "updated"}


@router.post("/developer/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str, request: Request):
    """Send a test event to a webhook endpoint."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    sub = _webhooks.get(webhook_id)
    if not sub or sub.user_id != user_id:
        raise HTTPException(404, "Webhook not found")

    test_payload = {
        "event": "webhook.test",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"message": "This is a test webhook delivery from Omni OS"},
    }

    result = await deliver_webhook(sub, "webhook.test", test_payload)
    return result


@router.get("/developer/webhooks/{webhook_id}/deliveries")
async def get_webhook_deliveries(webhook_id: str, request: Request, limit: int = 20):
    """Get recent delivery attempts for a webhook."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    sub = _webhooks.get(webhook_id)
    if not sub or sub.user_id != user_id:
        raise HTTPException(404, "Webhook not found")

    deliveries = [d for d in _webhook_deliveries if d.webhook_id == webhook_id]
    return {"deliveries": deliveries[-limit:]}


@router.get("/developer/webhooks/events")
async def list_webhook_events(request: Request):
    """List all available webhook event types."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return {"events": sorted(VALID_WEBHOOK_EVENTS - {"*"})}


async def deliver_webhook(sub: WebhookSubscription, event_type: str, payload: dict) -> dict:
    """Deliver a webhook payload to a subscription endpoint."""
    body = json.dumps(payload, default=str)
    signature = hmac.new(sub.secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Omni-Event": event_type,
        "X-Omni-Signature": f"sha256={signature}",
        "X-Omni-Delivery": f"del_{uuid4().hex[:12]}",
        "User-Agent": "OmniOS-Webhook/1.0",
    }

    delivery = WebhookDelivery(webhook_id=sub.id, event_type=event_type, payload=payload)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(sub.url, content=body, headers=headers)
            delivery.status_code = resp.status_code
            delivery.response_body = resp.text[:500]
            delivery.success = 200 <= resp.status_code < 300

            sub.last_delivered_at = datetime.utcnow().isoformat()
            sub.last_status_code = resp.status_code

            if not delivery.success:
                sub.failure_count += 1
            else:
                sub.failure_count = 0
    except Exception as exc:
        delivery.status_code = 0
        delivery.response_body = str(exc)[:500]
        delivery.success = False
        sub.failure_count += 1

    _webhook_deliveries.append(delivery)
    if len(_webhook_deliveries) > MAX_DELIVERY_LOG:
        _webhook_deliveries.pop(0)

    return {
        "delivered": delivery.success,
        "status_code": delivery.status_code,
        "response": delivery.response_body[:200],
    }


async def dispatch_event(user_id: str, event_type: str, data: dict):
    """Dispatch an event to all matching webhook subscriptions for a user.
    Call this from agent engine, campaign runner, etc."""
    payload = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    for sub in _webhooks.values():
        if sub.user_id != user_id or not sub.active:
            continue
        if sub.failure_count >= 10:
            continue  # Auto-disabled after 10 consecutive failures
        if "*" in sub.events or event_type in sub.events:
            try:
                await deliver_webhook(sub, event_type, payload)
            except Exception as exc:
                logger.warning(f"Webhook delivery failed for {sub.id}: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. OAUTH PROVIDER — "Sign in with Omni"
# ═══════════════════════════════════════════════════════════════════════════════

class OAuthApp(BaseModel):
    id: str = Field(default_factory=lambda: f"app_{uuid4().hex[:12]}")
    client_id: str = Field(default_factory=lambda: f"omni_{secrets.token_urlsafe(16)}")
    client_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    user_id: str = ""  # owner
    name: str = ""
    redirect_uris: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=lambda: ["profile"])
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class OAuthAuthorizationCode(BaseModel):
    code: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    client_id: str
    user_id: str
    redirect_uri: str
    scopes: list[str]
    expires_at: float  # unix timestamp
    used: bool = False


class OAuthAccessToken(BaseModel):
    access_token: str = Field(default_factory=lambda: f"omni_at_{secrets.token_urlsafe(32)}")
    refresh_token: str = Field(default_factory=lambda: f"omni_rt_{secrets.token_urlsafe(32)}")
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""
    user_id: str = ""
    client_id: str = ""
    created_at: float = Field(default_factory=time.time)


class RegisterOAuthAppRequest(BaseModel):
    name: str
    redirect_uris: list[str]
    scopes: list[str] = Field(default_factory=lambda: ["profile"])


# In-memory stores
_oauth_apps: dict[str, OAuthApp] = {}  # app_id -> app
_oauth_client_index: dict[str, str] = {}  # client_id -> app_id
_oauth_codes: dict[str, OAuthAuthorizationCode] = {}  # code -> auth_code
_oauth_tokens: dict[str, OAuthAccessToken] = {}  # access_token -> token

VALID_OAUTH_SCOPES = {"profile", "agents", "campaigns", "webhooks"}


@router.post("/developer/oauth/apps")
async def register_oauth_app(req: RegisterOAuthAppRequest, request: Request):
    """Register a new OAuth application."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    # Validate redirect URIs
    for uri in req.redirect_uris:
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme not in ("https", "http"):
            raise HTTPException(400, f"Invalid redirect URI: {uri}")

    invalid = set(req.scopes) - VALID_OAUTH_SCOPES
    if invalid:
        raise HTTPException(400, f"Invalid scopes: {invalid}")

    app = OAuthApp(user_id=user_id, name=req.name, redirect_uris=req.redirect_uris, scopes=req.scopes)
    _oauth_apps[app.id] = app
    _oauth_client_index[app.client_id] = app.id

    return {
        "id": app.id,
        "client_id": app.client_id,
        "client_secret": app.client_secret,
        "name": app.name,
        "redirect_uris": app.redirect_uris,
        "scopes": app.scopes,
        "message": "Save the client_secret — it won't be shown again.",
    }


@router.get("/developer/oauth/apps")
async def list_oauth_apps(request: Request):
    """List registered OAuth apps."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    apps = [
        {"id": a.id, "client_id": a.client_id, "name": a.name,
         "redirect_uris": a.redirect_uris, "scopes": a.scopes, "created_at": a.created_at}
        for a in _oauth_apps.values() if a.user_id == user_id
    ]
    return {"apps": apps}


@router.delete("/developer/oauth/apps/{app_id}")
async def delete_oauth_app(app_id: str, request: Request):
    """Delete an OAuth application."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    app = _oauth_apps.get(app_id)
    if not app or app.user_id != user_id:
        raise HTTPException(404, "OAuth app not found")

    _oauth_client_index.pop(app.client_id, None)
    del _oauth_apps[app_id]
    return {"id": app_id, "status": "deleted"}


@router.get("/oauth/authorize")
async def oauth_authorize(
    client_id: str, redirect_uri: str, response_type: str = "code",
    scope: str = "profile", state: str = "", request: Request = None,
):
    """OAuth 2.0 Authorization endpoint. Returns an authorization code."""
    if response_type != "code":
        raise HTTPException(400, "Only response_type=code is supported")

    app_id = _oauth_client_index.get(client_id)
    if not app_id:
        raise HTTPException(400, "Invalid client_id")
    app = _oauth_apps[app_id]

    if redirect_uri not in app.redirect_uris:
        raise HTTPException(400, "redirect_uri not registered for this application")

    user_id = get_user_id(request) if request else None
    if not user_id:
        raise HTTPException(401, "User must be authenticated to authorize")

    requested_scopes = scope.split()
    invalid = set(requested_scopes) - VALID_OAUTH_SCOPES
    if invalid:
        raise HTTPException(400, f"Invalid scopes: {invalid}")

    auth_code = OAuthAuthorizationCode(
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scopes=requested_scopes,
        expires_at=time.time() + 600,  # 10 min
    )
    _oauth_codes[auth_code.code] = auth_code

    # Build redirect
    params = {"code": auth_code.code}
    if state:
        params["state"] = state

    redirect_url = f"{redirect_uri}?{urllib.parse.urlencode(params)}"
    return {"redirect_url": redirect_url, "code": auth_code.code}


@router.post("/oauth/token")
async def oauth_token(request: Request):
    """OAuth 2.0 Token endpoint. Exchange code for access token."""
    body = await request.json()
    grant_type = body.get("grant_type", "")

    if grant_type == "authorization_code":
        code = body.get("code", "")
        client_id = body.get("client_id", "")
        client_secret = body.get("client_secret", "")
        redirect_uri = body.get("redirect_uri", "")

        auth_code = _oauth_codes.get(code)
        if not auth_code or auth_code.used:
            raise HTTPException(400, "Invalid or expired authorization code")

        if time.time() > auth_code.expires_at:
            raise HTTPException(400, "Authorization code expired")

        if auth_code.client_id != client_id:
            raise HTTPException(400, "client_id mismatch")

        if auth_code.redirect_uri != redirect_uri:
            raise HTTPException(400, "redirect_uri mismatch")

        # Verify client secret
        app_id = _oauth_client_index.get(client_id)
        app = _oauth_apps.get(app_id, None) if app_id else None
        if not app or app.client_secret != client_secret:
            raise HTTPException(401, "Invalid client credentials")

        auth_code.used = True

        token = OAuthAccessToken(
            scope=" ".join(auth_code.scopes),
            user_id=auth_code.user_id,
            client_id=client_id,
        )
        _oauth_tokens[token.access_token] = token

        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "scope": token.scope,
        }

    elif grant_type == "refresh_token":
        refresh = body.get("refresh_token", "")
        client_id = body.get("client_id", "")
        client_secret = body.get("client_secret", "")

        # Find the token with this refresh token
        old_token = None
        for t in _oauth_tokens.values():
            if t.refresh_token == refresh and t.client_id == client_id:
                old_token = t
                break

        if not old_token:
            raise HTTPException(400, "Invalid refresh token")

        app_id = _oauth_client_index.get(client_id)
        app = _oauth_apps.get(app_id, None) if app_id else None
        if not app or app.client_secret != client_secret:
            raise HTTPException(401, "Invalid client credentials")

        # Issue new token
        _oauth_tokens.pop(old_token.access_token, None)
        new_token = OAuthAccessToken(
            scope=old_token.scope,
            user_id=old_token.user_id,
            client_id=client_id,
        )
        _oauth_tokens[new_token.access_token] = new_token

        return {
            "access_token": new_token.access_token,
            "refresh_token": new_token.refresh_token,
            "token_type": new_token.token_type,
            "expires_in": new_token.expires_in,
            "scope": new_token.scope,
        }

    else:
        raise HTTPException(400, f"Unsupported grant_type: {grant_type}")


@router.get("/oauth/userinfo")
async def oauth_userinfo(request: Request):
    """OAuth 2.0 UserInfo endpoint. Returns user profile for a valid access token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")

    access_token = auth[7:]
    token = _oauth_tokens.get(access_token)
    if not token:
        raise HTTPException(401, "Invalid access token")

    if time.time() > token.created_at + token.expires_in:
        raise HTTPException(401, "Access token expired")

    return {
        "sub": token.user_id,
        "scope": token.scope,
        "client_id": token.client_id,
        "issued_at": datetime.fromtimestamp(token.created_at).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API VERSIONING & METADATA
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/developer/info")
async def developer_info(request: Request):
    """Developer platform information and API documentation links."""
    return {
        "platform": "Omni OS",
        "api_version": "v1",
        "docs": {
            "openapi": "/openapi.json",
            "redoc": "/redoc",
            "swagger": "/docs",
        },
        "endpoints": {
            "api_keys": "/developer/api-keys",
            "webhooks": "/developer/webhooks",
            "oauth_apps": "/developer/oauth/apps",
            "oauth_authorize": "/oauth/authorize",
            "oauth_token": "/oauth/token",
            "oauth_userinfo": "/oauth/userinfo",
            "marketplace": "/marketplace",
            "agents": "/agents",
            "campaigns": "/campaign/run",
        },
        "rate_limits": {
            "default": "1000 requests/hour per API key",
            "campaigns": "5/hour",
            "agents": "20/hour",
            "webhooks": "1000/hour",
        },
        "scopes": {
            "api_keys": sorted(VALID_SCOPES),
            "oauth": sorted(VALID_OAUTH_SCOPES),
            "webhook_events": sorted(VALID_WEBHOOK_EVENTS - {"*"}),
        },
    }
