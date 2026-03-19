"""
Omni OS Backend -- FastAPI Application
Slim entrypoint: middleware, lifecycle events, and router registration.
All endpoint logic lives in routes/*.py modules.
"""
from __future__ import annotations
import json
import logging
import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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

app = FastAPI(
    title="Omni OS API",
    description="Autonomous Agency Platform -- Backend Orchestration",
    version="0.3.0",
)

# CORS: default to localhost in dev, restrict in production via CORS_ORIGINS env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)
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
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/",
    )
    return response


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
    register_default_jobs()
    scheduler.start()
    logger.info("Background scheduler started")

    _register_event_bus_actions()

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
    """Stop background scheduler."""
    scheduler.stop()
    logger.info("Background scheduler stopped")


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Omni OS API -- {len(AGENTS)} agents, {len(settings.active_providers)} providers")
    uvicorn.run(app, host=settings.host, port=settings.port)
