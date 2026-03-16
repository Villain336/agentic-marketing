"""
Supervisor Backend — Authentication Middleware
Validates Supabase JWTs on protected endpoints.
Public endpoints (health, webhooks) are exempt.
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings

logger = logging.getLogger("supervisor.auth")

# Endpoints that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

PUBLIC_PREFIXES = (
    "/webhooks/",   # Webhook receivers use their own auth (signatures)
)

security = HTTPBearer(auto_error=False)


def _decode_jwt(token: str) -> Optional[dict]:
    """Decode and validate a Supabase JWT. Returns payload or None."""
    try:
        import jwt as pyjwt
    except ImportError:
        logger.warning("PyJWT not installed — auth disabled. pip install PyJWT")
        return {"sub": "dev-mode", "role": "authenticated"}

    secret = settings.supabase_jwt_secret
    if not secret:
        logger.warning("SUPABASE_JWT_SECRET not set — auth disabled")
        return {"sub": "dev-mode", "role": "authenticated"}

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


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates Supabase JWT on every request (except public paths)."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public endpoints
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Skip auth for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth entirely if JWT secret is not configured (dev mode)
        if not settings.supabase_jwt_secret:
            request.state.user_id = "dev-mode"
            request.state.user_role = "authenticated"
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
            )

        token = auth_header[7:]  # Strip "Bearer "
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


def get_user_id(request: Request) -> str:
    """Extract user_id from authenticated request."""
    return getattr(request.state, "user_id", "")


def require_auth(request: Request) -> str:
    """Dependency that ensures authentication and returns user_id."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id
