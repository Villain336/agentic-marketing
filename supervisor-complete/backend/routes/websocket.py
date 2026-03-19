"""WebSocket endpoints for real-time campaign and portfolio feeds."""
from __future__ import annotations
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from scoring import scorer
from ws import ws_manager
from store import store

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/campaign/{campaign_id}")
async def ws_campaign_feed(websocket: WebSocket, campaign_id: str):
    """Real-time feed for a specific campaign -- agent status, metrics, triggers."""
    await ws_manager.connect(websocket, campaign_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "refresh_scores":
                # Use cross-tenant lookup for WebSocket (already authenticated at connect)
                campaign = store.get_campaign_any_tenant(campaign_id)
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
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
