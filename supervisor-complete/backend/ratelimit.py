"""
Omni OS Backend — Rate Limiting
Per-user and per-campaign rate limiting with sliding window.
"""
from __future__ import annotations
import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("supervisor.ratelimit")


class SlidingWindowCounter:
    """Simple sliding window rate limiter."""

    def __init__(self):
        # key -> list of timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = 0.0
        self._cleanup_interval: float = 300.0  # 5 minutes

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if a request is allowed under the rate limit."""
        now = time.time()
        cutoff = now - window_seconds

        # Periodic cleanup of stale keys to prevent unbounded memory growth
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now, window_seconds)
            self._last_cleanup = now

        # Clean expired entries
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

        if len(self._windows[key]) >= max_requests:
            return False

        self._windows[key].append(now)
        return True

    def _cleanup(self, now: float, default_window: int = 3600) -> None:
        """Remove keys with no recent activity to prevent memory leaks."""
        cutoff = now - default_window
        stale_keys = [k for k, ts in self._windows.items() if not ts or max(ts) < cutoff]
        for k in stale_keys:
            del self._windows[k]

    def remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        """Get remaining requests in window."""
        now = time.time()
        cutoff = now - window_seconds
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]
        return max(0, max_requests - len(self._windows[key]))

    def reset_time(self, key: str, window_seconds: int) -> float:
        """Get seconds until window resets."""
        if not self._windows[key]:
            return 0
        oldest = min(self._windows[key])
        return max(0, (oldest + window_seconds) - time.time())


# Rate limit configurations per endpoint pattern
RATE_LIMITS = {
    # Campaign execution — expensive (LLM calls)
    "/campaign/run": {"max": 5, "window": 3600, "scope": "user"},
    "/agent/": {"max": 20, "window": 3600, "scope": "user"},
    "/templates/": {"max": 10, "window": 3600, "scope": "user"},
    "/campaigns/parallel": {"max": 3, "window": 3600, "scope": "user"},
    # Validation — moderate
    "/validate": {"max": 30, "window": 3600, "scope": "user"},
    # Webhooks — generous (external services)
    "/webhooks/": {"max": 1000, "window": 3600, "scope": "ip"},
    # Read endpoints — generous
    "/campaign/": {"max": 200, "window": 3600, "scope": "user"},
    # Default
    "_default": {"max": 100, "window": 3600, "scope": "user"},
}

_limiter = SlidingWindowCounter()


def _get_limit_config(path: str) -> dict:
    """Find the matching rate limit config for a path."""
    for pattern, config in RATE_LIMITS.items():
        if pattern == "_default":
            continue
        if path.startswith(pattern) or pattern in path:
            return config
    return RATE_LIMITS["_default"]


def _get_key(request: Request, scope: str) -> str:
    """Build the rate limit key based on scope."""
    if scope == "user":
        user_id = getattr(request.state, "user_id", "")
        return f"user:{user_id or request.client.host}"
    elif scope == "ip":
        return f"ip:{request.client.host}"
    elif scope == "campaign":
        # Extract campaign_id from path
        parts = request.url.path.split("/")
        campaign_id = ""
        for i, p in enumerate(parts):
            if p == "campaign" and i + 1 < len(parts):
                campaign_id = parts[i + 1]
                break
        return f"campaign:{campaign_id or request.client.host}"
    return f"global:{request.client.host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with sliding window counters."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for health, docs, websockets
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        if path.startswith("/ws/"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        config = _get_limit_config(path)
        key = _get_key(request, config["scope"])
        # Use matched route pattern (e.g. /campaigns/{id}/run) to avoid
        # collapsing different endpoints into the same bucket
        route = getattr(request.scope.get("route"), "path", None)
        route_key = route or path.split("/")[1]
        full_key = f"{key}:{route_key}"

        if not _limiter.is_allowed(full_key, config["max"], config["window"]):
            remaining = _limiter.remaining(full_key, config["max"], config["window"])
            reset = _limiter.reset_time(full_key, config["window"])
            logger.warning(f"Rate limit exceeded: {full_key}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": config["max"],
                    "window_seconds": config["window"],
                    "retry_after": int(reset),
                },
                headers={
                    "X-RateLimit-Limit": str(config["max"]),
                    "X-RateLimit-Remaining": str(remaining),
                    "Retry-After": str(int(reset)),
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        remaining = _limiter.remaining(full_key, config["max"], config["window"])
        response.headers["X-RateLimit-Limit"] = str(config["max"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
