"""Computer Use — Live Browser Streaming, Multi-Browser, Recordings, Handoff."""
from __future__ import annotations
import json

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from computer_use import browser_pool
from auth import get_user_id

router = APIRouter(prefix="/browser", tags=["Browser"])


@router.post("/sessions")
async def create_browser_session(request: Request):
    """Launch a live browser session for an agent with real-time streaming."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    session = await browser_pool.create_session(
        agent_id=payload.get("agent_id", ""),
        campaign_id=payload.get("campaign_id", ""),
        start_url=payload.get("start_url", ""),
        viewport=payload.get("viewport"),
        proxy=payload.get("proxy", ""),
        recording=payload.get("recording", True),
    )
    return session.to_dict()


@router.get("/sessions")
async def list_browser_sessions(request: Request, campaign_id: str = "", agent_id: str = "", status: str = ""):
    """List browser sessions with optional filters."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return {"sessions": browser_pool.list_sessions(campaign_id, agent_id, status)}


@router.get("/sessions/{session_id}")
async def get_browser_session(session_id: str, request: Request):
    """Get details of a specific browser session."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    session = browser_pool.get_session(session_id)
    if not session:
        raise HTTPException(404, "Browser session not found")
    return session


@router.post("/sessions/{session_id}/action")
async def execute_browser_action(session_id: str, request: Request):
    """Execute a browser action (click, type, navigate, etc.) in a live session."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    from computer_use import BrowserAction, ActionType
    coords = None
    if payload.get("coordinates"):
        coords = tuple(payload["coordinates"])
    action = BrowserAction(
        action_type=ActionType(payload["action_type"]),
        selector=payload.get("selector", ""),
        value=payload.get("value", ""),
        coordinates=coords,
        description=payload.get("description", ""),
    )
    result = await browser_pool.execute_action(session_id, action)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/vision-step")
async def vision_navigate_step(session_id: str, request: Request):
    """Execute one vision-guided navigation step: screenshot -> vision model -> action."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    result = await browser_pool.vision_step(
        session_id, payload["goal"], payload.get("screenshot_b64", "")
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/vision-plan")
async def vision_plan_steps(session_id: str, request: Request):
    """Plan a full multi-step browser interaction using vision analysis."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    session = browser_pool._sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Browser session not found")
    plan = await browser_pool._vision.plan_multi_step(
        payload.get("screenshot_b64", ""), payload["goal"], payload.get("max_steps", 20)
    )
    return {"session_id": session_id, "plan": plan}


@router.post("/parallel")
async def launch_parallel_browsers(request: Request):
    """Launch multiple browser sessions simultaneously — N agents, N browsers."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    result = await browser_pool.run_parallel_sessions(payload["tasks"])
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/handoff")
async def request_human_handoff(session_id: str, request: Request):
    """Agent yields browser control to human."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    result = await browser_pool.request_human_handoff(
        session_id, payload["reason"], payload.get("notify_channels")
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/takeover")
async def human_takeover(session_id: str, request: Request):
    """Human assumes direct browser control during a live session."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    result = await browser_pool.human_takeover(session_id, user_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/release")
async def human_release(session_id: str, request: Request):
    """Human returns browser control to agent."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    result = await browser_pool.human_release(session_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/human-action")
async def human_browser_action(session_id: str, request: Request):
    """Execute a human-initiated browser action during takeover mode."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    result = await browser_pool.human_action(
        session_id, payload["action_type"],
        payload.get("selector", ""), payload.get("value", ""),
        tuple(payload["coordinates"]) if payload.get("coordinates") else None,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/close")
async def close_browser_session(session_id: str, request: Request):
    """Close a browser session and finalize its recording."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    result = await browser_pool.close_session(session_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/dashboard")
async def browser_dashboard(request: Request):
    """Multi-browser control panel — all active sessions, streams, and stats."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return browser_pool.get_dashboard()


@router.get("/stats")
async def browser_stats(request: Request):
    """Aggregate statistics across all browser sessions."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return browser_pool.get_stats()


@router.get("/recordings")
async def list_recordings(request: Request, campaign_id: str = "", agent_id: str = ""):
    """List all browser session recordings."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return {"recordings": browser_pool.list_recordings(campaign_id, agent_id)}


@router.get("/recordings/{recording_id}")
async def get_recording(recording_id: str, request: Request, format: str = "json"):
    """Get or export a browser session recording."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    result = await browser_pool.export_recording(recording_id, format)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/recordings/{recording_id}/annotate")
async def annotate_recording(recording_id: str, request: Request):
    """Add human annotation to a specific frame in a recording."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    payload = await request.json()
    result = await browser_pool.annotate_recording(
        recording_id, payload["frame_index"], payload["annotation"], payload.get("author", "user")
    )
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# Browser stream WebSocket needs to be on the main app since prefix doesn't apply to websockets
# in all FastAPI versions consistently. We register it separately.

async def browser_stream_ws(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for live browser session streaming."""
    await websocket.accept()
    await browser_pool.subscribe_to_stream(session_id, websocket)

    session = browser_pool.get_session(session_id)
    if session:
        await websocket.send_json({
            "type": "session_state",
            "session": session,
            "message": "Connected to live browser stream. You will see all agent actions in real-time.",
        })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "human_action":
                s = browser_pool._sessions.get(session_id)
                if s and s.human_control:
                    await browser_pool.human_action(
                        session_id, msg["action_type"],
                        msg.get("selector", ""), msg.get("value", ""),
                        tuple(msg["coordinates"]) if msg.get("coordinates") else None,
                    )
    except WebSocketDisconnect:
        await browser_pool.unsubscribe_from_stream(session_id, websocket)
