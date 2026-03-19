"""
Omni OS Backend — Authentication & Authorization
Validates Supabase JWTs on protected endpoints.
Public endpoints (health, webhooks, docs) are exempt.
"""
from __future__ import annotations
import logging
import re
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from config import settings

logger = logging.getLogger("supervisor.auth")

# ── Public paths (no auth required) ─────────────────────────────────────────

PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/session",
    "/auth/logout",
    "/metrics",
    "/metrics/json",
}

PUBLIC_PREFIXES = (
    "/webhooks/",          # Webhook receivers use their own auth (signatures)
    "/mcp/",               # MCP clients handle auth at transport level
    "/billing/webhook",    # Stripe webhooks use signature verification
)

security = HTTPBearer(auto_error=False)


# ── JWT Decoding ─────────────────────────────────────────────────────────────

def _decode_jwt(token: str) -> Optional[dict]:
    """Decode and validate a Supabase JWT. Returns payload or None."""
    try:
        import jwt as pyjwt
    except ImportError:
        logger.warning("PyJWT not installed -- install with: pip install PyJWT")
        return None

    secret = settings.supabase_jwt_secret
    if not secret:
        logger.warning("SUPABASE_JWT_SECRET not set -- JWT validation skipped")
        return None

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except pyjwt.InvalidTokenError as e:
        logger.debug(f"JWT invalid: {e}")
        return None


# ── Auth Middleware ───────────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """Validates Supabase JWT on every request (except public paths).
    Always sets request.state.user_id for downstream use.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public endpoints
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            request.state.user_id = ""
            request.state.user_role = ""
            return await call_next(request)

        # Skip auth for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Dev mode: allow unauthenticated access only from localhost
        if not settings.supabase_jwt_secret:
            client_host = request.client.host if request.client else ""
            if client_host in ("127.0.0.1", "::1", "localhost"):
                request.state.user_id = "dev-local"
                request.state.user_role = "authenticated"
                return await call_next(request)
            logger.warning("SUPABASE_JWT_SECRET not set and request from non-localhost: %s", client_host)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication not configured. Set SUPABASE_JWT_SECRET."},
            )

        # Extract token: prefer httpOnly cookie, fall back to Bearer header
        token = request.cookies.get("omni_session")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization (cookie or Bearer header)"},
            )

        payload = _decode_jwt(token)

        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Attach user info to request state for use in endpoints
        request.state.user_id = payload.get("sub", "")
        request.state.user_role = payload.get("role", "")

        return await call_next(request)


# ── Dependency helpers ───────────────────────────────────────────────────────

def get_user_id(request: Request) -> str:
    """Extract user_id from authenticated request."""
    return getattr(request.state, "user_id", "")


def get_user_role(request: Request) -> str:
    """Extract user role from authenticated request."""
    return getattr(request.state, "user_role", "")


def require_auth(request: Request) -> str:
    """Dependency that ensures authentication and returns user_id.
    Use as: user_id: str = Depends(require_auth)
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


def require_role(request: Request, *allowed_roles: str) -> str:
    """Dependency that ensures the user has one of the allowed roles.
    Use as: user_id = require_role(request, "admin", "service_role")
    """
    user_id = require_auth(request)
    role = get_user_role(request)
    if role not in allowed_roles and role != "service_role":
        raise HTTPException(403, f"Role '{role}' not authorized for this action")
    return user_id


# ── Input Validation Helpers ─────────────────────────────────────────────────

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_SAFE_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def validate_id(value: str, field_name: str = "id") -> str:
    """Validate that a path/query parameter is a safe identifier."""
    if not value or not _SAFE_ID.match(value):
        raise HTTPException(400, f"Invalid {field_name}: must be alphanumeric, 1-128 chars")
    return value


def validate_campaign_id(campaign_id: str) -> str:
    """Validate campaign ID format (UUID)."""
    if not campaign_id or not (_SAFE_UUID.match(campaign_id) or _SAFE_ID.match(campaign_id)):
        raise HTTPException(400, "Invalid campaign_id format")
    return campaign_id


def safe_setattr(obj: object, key: str, value, allowed_fields: set[str]) -> bool:
    """Safe alternative to setattr() — only sets allowed fields.
    Prevents arbitrary attribute injection.
    """
    if key not in allowed_fields:
        return False
    if not hasattr(obj, key):
        return False
    setattr(obj, key, value)
    return True


# Set of fields that are safe to update on CampaignMemory via API
MEMORY_WRITABLE_FIELDS = {
    "prospects", "prospect_count", "email_sequence", "content_strategy",
    "social_calendar", "ad_package", "cs_system", "cs_complete",
    "site_launch_brief", "campaign_complete", "legal_playbook",
    "gtm_strategy", "tool_stack", "newsletter_system", "ppc_playbook",
    "financial_plan", "hr_playbook", "sales_playbook", "delivery_system",
    "analytics_framework", "treasury_plan", "tax_playbook", "wealth_strategy",
    "billing_system", "referral_program", "upsell_playbook",
    "competitive_intel", "client_portal", "voice_receptionist",
    "fullstack_dev_output", "economist_briefing", "pr_communications",
    "data_dashboards", "governance_brief", "product_roadmap",
    "partnerships_playbook", "client_fulfillment", "agent_workspace",
    "genome_intel",
}
