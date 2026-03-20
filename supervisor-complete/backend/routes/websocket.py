"""WebSocket endpoints for real-time campaign and portfolio feeds."""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from scoring import scorer
from ws import ws_manager
from store import store

logger = logging.getLogger("supervisor.ws")

router = APIRouter(tags=["WebSocket"])


def _ws_authenticate(websocket: WebSocket) -> str:
    """Extract auth token from WebSocket query params or headers.
    Returns user_id or empty string if unauthenticated.
    """
    # WebSocket auth via query param: ?token=<jwt>
    token = websocket.query_params.get("token", "")
    if not token:
        # Fall back to Sec-WebSocket-Protocol header
        token = websocket.headers.get("authorization", "").replace("Bearer ", "")

    if not token:
        return ""

    from auth import _decode_jwt
    from config import settings
    if not settings.supabase_jwt_secret:
        # Dev mode — allow if from localhost
        client_host = websocket.client.host if websocket.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost"):
            return "dev-local"
        return ""

    payload = _decode_jwt(token)
    if payload:
        return payload.get("sub", "")
    return ""


@router.websocket("/ws/campaign/{campaign_id}")
async def ws_campaign_feed(websocket: WebSocket, campaign_id: str):
    """Real-time feed for a specific campaign -- agent status, metrics, triggers."""
    user_id = _ws_authenticate(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Verify campaign belongs to user
    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        await websocket.close(code=4004, reason="Campaign not found")
        return

    await ws_manager.connect(websocket, campaign_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "refresh_scores":
                campaign = store.get_campaign(user_id, campaign_id)
                if campaign:
                    scores = scorer.score_all(campaign)
                    await websocket.send_text(json.dumps({
                        "type": "score_update", "scores": {
                            k: {"score": v["score"], "grade": v["grade"]}
                            for k, v in scores.items()
                        },
                    }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, campaign_id)


@router.websocket("/ws/portfolio")
async def ws_portfolio_feed(websocket: WebSocket):
    """Real-time feed for portfolio-level events across all campaigns."""
    user_id = _ws_authenticate(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
