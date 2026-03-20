"""
Omni OS Backend -- FastAPI Application
Slim entrypoint: middleware, lifecycle events, and router registration.
All endpoint logic lives in routes/*.py modules.
"""
from __future__ import annotations
import json
import logging
import os
import time

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings
from agents import AGENTS, get_agent
from scheduler import scheduler, register_default_jobs
from auth import AuthMiddleware
from ws import ws_manager
from ratelimit import RateLimitMiddleware
from observability import MetricsMiddleware, metrics
from genome import genome
from store import store
import db

from routes import all_routers
from routes.browser import browser_stream_ws

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnios.api")


# -- Error Normalization Middleware (Fix 5) ------------------------------------

class ErrorNormalizationMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return sanitized error responses.
    Prevents leaking stack traces, API keys, or internal details to clients.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(
                "Unhandled exception on %s %s: %s",
                request.method, request.url.path, type(e).__name__,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error. Please try again later."},
            )


# -- Request/Response Logging Middleware ---------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        # Skip noisy paths
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return response

        logger.info(
            "%s %s -> %d (%dms) user=%s",
            request.method, path, response.status_code, duration_ms,
            getattr(request.state, "user_id", "-"),
        )
        return response


# -- Application ---------------------------------------------------------------

openapi_tags = [
    {"name": "Health", "description": "Liveness and readiness probes"},
    {"name": "WebSocket", "description": "Real-time WebSocket connections"},
    {"name": "Agents", "description": "Agent management and execution"},
    {"name": "Campaigns", "description": "Campaign CRUD and orchestration"},
    {"name": "Onboarding", "description": "New-user and new-campaign onboarding flows"},
    {"name": "Webhooks", "description": "Inbound webhook receivers"},
    {"name": "Approvals", "description": "Human-in-the-loop approval queue"},
    {"name": "Settings", "description": "Platform and user settings"},
    {"name": "Scoring & Lifecycle", "description": "Lead scoring and lifecycle tracking"},
    {"name": "Budget", "description": "Budget allocation and tracking"},
    {"name": "Templates", "description": "Campaign templates"},
    {"name": "Tenants", "description": "Multi-tenant management"},
    {"name": "Revenue Share", "description": "Revenue-share and payouts"},
    {"name": "Skills", "description": "Agent skill registry"},
    {"name": "Marketplace", "description": "Agent and skill marketplace"},
    {"name": "WhatsApp", "description": "WhatsApp messaging integration"},
    {"name": "Replanner", "description": "Autonomous campaign re-planning"},
    {"name": "Deployment", "description": "Deployment and infrastructure management"},
    {"name": "Privacy", "description": "Privacy controls and data subject requests"},
    {"name": "Fine-tuning", "description": "Model fine-tuning jobs"},
    {"name": "Research", "description": "Research and competitive intelligence"},
    {"name": "Design", "description": "Design asset generation"},
    {"name": "Browser", "description": "Headless browser automation"},
    {"name": "Manufacturing", "description": "Manufacturing and supply-chain tools"},
    {"name": "Security", "description": "Security scanning and compliance"},
    {"name": "NVIDIA", "description": "NVIDIA GPU and AI acceleration"},
    {"name": "AWS", "description": "AWS cloud service integrations"},
    {"name": "Reindustrialization", "description": "Reindustrialization planning tools"},
    {"name": "Integrations", "description": "Third-party service integrations"},
    {"name": "Developer Platform", "description": "Developer APIs and SDK support"},
    {"name": "Agent Protocol", "description": "AI Agent Protocol (A2A) endpoints"},
    {"name": "MCP", "description": "Model Context Protocol server interface"},
]

app = FastAPI(
    title="Omni OS API",
    description="Autonomous Agency Platform -- Backend Orchestration",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=openapi_tags,
)

# CORS: restricted methods and headers for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With",
                   "Accept", "Origin", "X-API-Key", "X-Campaign-ID"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(ErrorNormalizationMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# -- Register all route modules ------------------------------------------------
for router in all_routers:
    app.include_router(router)

# -- Session Cookie Endpoints --------------------------------------------------

from fastapi.responses import Response as FastAPIResponse
from auth import _decode_jwt

@app.post("/auth/session")
async def create_session(request: Request):
    """Exchange a Bearer token for an httpOnly secure session cookie."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing Bearer token"})

    token = auth_header[7:]
    if settings.supabase_jwt_secret:
        payload = _decode_jwt(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        key="omni_session",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24,  # 24 hours (reduced from 7 days for security)
        path="/",
    )
    return response


# -- Emergency Kill Switch API (ASI-10 / MEDIUM-02 fix) -----------------------

from engine import kill_agent, kill_campaign, revive_agent, revive_campaign, list_killed
from auth import require_permission

@app.post("/admin/kill-agent", tags=["Security"])
async def api_kill_agent(
    campaign_id: str, agent_id: str,
    _user=Depends(require_permission("admin", "write")),
):
    """Emergency halt a specific agent in a campaign."""
    kill_agent(campaign_id, agent_id)
    return {"status": "killed", "campaign_id": campaign_id, "agent_id": agent_id}


@app.post("/admin/kill-campaign", tags=["Security"])
async def api_kill_campaign(
    campaign_id: str,
    _user=Depends(require_permission("admin", "write")),
):
    """Emergency halt all agents in a campaign."""
    kill_campaign(campaign_id)
    return {"status": "killed", "campaign_id": campaign_id}


@app.post("/admin/revive-agent", tags=["Security"])
async def api_revive_agent(
    campaign_id: str, agent_id: str,
    _user=Depends(require_permission("admin", "write")),
):
    """Remove kill switch for a specific agent."""
    revive_agent(campaign_id, agent_id)
    return {"status": "revived", "campaign_id": campaign_id, "agent_id": agent_id}


@app.post("/admin/revive-campaign", tags=["Security"])
async def api_revive_campaign(
    campaign_id: str,
    _user=Depends(require_permission("admin", "write")),
):
    """Remove campaign-level kill switch."""
    revive_campaign(campaign_id)
    return {"status": "revived", "campaign_id": campaign_id}


@app.get("/admin/kill-switches", tags=["Security"])
async def api_list_kills(
    _user=Depends(require_permission("admin", "read")),
):
    """List all active kill switches."""
    return list_killed()


@app.post("/auth/logout")
async def logout_session():
    """Clear the session cookie."""
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(key="omni_session", path="/")
    return response


# -- WebSocket that can't use prefix-based routers cleanly ---------------------
@app.websocket("/ws/browser/{session_id}/stream")
async def _browser_stream_ws(websocket: WebSocket, session_id: str):
    await browser_stream_ws(websocket, session_id)


# -- Event Bus Action Handlers ------------------------------------------------

def _register_event_bus_actions():
    """Register action handlers for event bus trigger rules."""
    from eventbus import event_bus, Event

    async def _handle_run_agent(event: Event):
        target_agent_id = event.data.get("_target_agent", "")
        campaign_id = event.campaign_id
        if not target_agent_id or not campaign_id:
            return
        campaign = store.get_campaign_any_tenant(campaign_id)
        if not campaign:
            return
        agent = get_agent(target_agent_id)
        if not agent:
            logger.warning(f"Event trigger: agent '{target_agent_id}' not found")
            return

        existing_run = campaign.agent_runs.get(target_agent_id)
        if existing_run and existing_run.status in ("running",):
            logger.info(f"Event trigger: {target_agent_id} already running, skipping")
            return

        logger.info(
            f"Event trigger: running {target_agent_id} "
            f"(triggered by {event.source_agent} via {event.data.get('_trigger_name', '?')})"
        )

        try:
            from engine import engine as eng
            async for ev in eng.run(
                agent=agent, memory=campaign.memory,
                campaign_id=campaign_id, campaign=campaign,
                trigger_reason=f"event:{event.data.get('_trigger_name', '')}",
            ):
                if ev.memory_update:
                    for k, v in ev.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
                try:
                    await ws_manager.broadcast({
                        "type": "agent_event",
                        "campaign_id": campaign_id,
                        "agent_id": target_agent_id,
                        "event": ev.model_dump(),
                        "triggered_by": event.source_agent,
                    })
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Event-triggered agent {target_agent_id} failed: {e}")

    async def _handle_notify(event: Event):
        target_data = event.data.get("_target_data", {})
        template = target_data.get("template", "generic")
        campaign_id = event.campaign_id

        msg = (
            f"[{template.upper()}] Agent: {event.source_agent} | "
            f"Campaign: {campaign_id} | "
            f"Event: {event.type.value if hasattr(event.type, 'value') else event.type}"
        )

        from tools import registry
        for tool_name in ["send_slack_message", "send_telegram_message", "send_email"]:
            try:
                if tool_name == "send_slack_message":
                    await registry.execute(tool_name, {"channel": "#alerts", "message": msg}, "notify")
                elif tool_name == "send_telegram_message":
                    await registry.execute(tool_name, {"message": msg}, "notify")
                break
            except Exception:
                continue

    async def _handle_pause_agent(event: Event):
        target_agent_id = event.data.get("_target_agent", "")
        campaign_id = event.campaign_id
        logger.info(f"Event trigger: pausing {target_agent_id} in campaign {campaign_id}")
        campaign = store.get_campaign_any_tenant(campaign_id)
        if campaign and target_agent_id in campaign.agent_runs:
            campaign.agent_runs[target_agent_id].status = "paused"

    event_bus.register_action("run_agent", _handle_run_agent)
    event_bus.register_action("notify", _handle_notify)
    event_bus.register_action("pause_agent", _handle_pause_agent)
    logger.info("Event bus action handlers registered")


# -- Lifecycle Events ----------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Start background scheduler, register event handlers, load persisted data."""
    # ── Startup health checks ──
    _startup_warnings = []

    # Check required environment variables
    required_vars = {
        "supabase_url": settings.supabase_url,
        "supabase_service_key": settings.supabase_service_key,
        "supabase_jwt_secret": settings.supabase_jwt_secret,
    }
    for var_name, var_val in required_vars.items():
        if not var_val:
            _startup_warnings.append(f"MISSING: {var_name} not configured")

    # Check LLM provider availability
    active_providers = getattr(settings, 'active_providers', [])
    if not active_providers:
        _startup_warnings.append("WARNING: No LLM providers configured")
    else:
        logger.info(f"Startup: {len(active_providers)} LLM provider(s) active")

    # Check database connectivity
    if db.is_persistent():
        try:
            # Simple connectivity check
            await db.load_user_campaigns("__healthcheck__")
            logger.info("Startup: Supabase connection verified")
        except Exception as e:
            _startup_warnings.append(f"WARNING: Supabase connectivity issue: {type(e).__name__}")
    else:
        _startup_warnings.append("INFO: Running without persistent database")

    for warning in _startup_warnings:
        logger.warning(f"Startup check: {warning}")

    # HIGH-03 fix: In production, require JWT secret — refuse to start without it
    app_env = os.environ.get("APP_ENV", "development").lower()
    if app_env in ("production", "staging") and not settings.supabase_jwt_secret:
        logger.critical(
            "FATAL: SUPABASE_JWT_SECRET not set in %s environment. "
            "Auth middleware will bypass authentication. Refusing to start.", app_env
        )
        raise RuntimeError(
            f"SUPABASE_JWT_SECRET is required in {app_env}. "
            "Set this environment variable or use APP_ENV=development for local testing."
        )

    # ── Register event bus BEFORE starting scheduler to prevent race ──
    _register_event_bus_actions()

    register_default_jobs()
    scheduler.start()
    logger.info("Background scheduler started")

    try:
        if db.is_persistent():
            dna_count = await genome.load_from_db()
            logger.info(f"Startup: loaded {dna_count} genome DNA entries from DB")
        else:
            logger.info("No persistent DB configured -- starting with empty campaign store")
    except Exception as e:
        logger.warning(f"Failed to load persisted data on startup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown: flush pending work, stop scheduler."""
    logger.info("Shutdown initiated — flushing pending work...")

    # Flush pending campaign memory to DB
    try:
        for campaign in store.all_campaigns():
            if db.is_persistent() and hasattr(campaign, 'id') and hasattr(campaign, 'memory'):
                from store import serialize_memory
                await db.update_campaign_memory(campaign.id, serialize_memory(campaign.memory))
    except Exception as e:
        logger.warning(f"Shutdown: failed to flush campaign memory: {e}")

    scheduler.stop()
    logger.info("Background scheduler stopped — shutdown complete")


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Omni OS API -- {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
