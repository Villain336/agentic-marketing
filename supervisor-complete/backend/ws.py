"""
Omni OS Backend — WebSocket Manager
Real-time push for agent status, metrics, and campaign events.
Replaces polling with live updates.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("supervisor.ws")


class ConnectionManager:
    """Manages WebSocket connections per campaign and broadcasts events."""

    def __init__(self):
        # campaign_id -> list of active websocket connections
        self._connections: dict[str, list[WebSocket]] = {}
        # Global connections (portfolio-level)
        self._global: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, campaign_id: str = ""):
        await websocket.accept()
        if campaign_id:
            if campaign_id not in self._connections:
                self._connections[campaign_id] = []
            self._connections[campaign_id].append(websocket)
            logger.debug(f"WS connected to campaign {campaign_id}")
        else:
            self._global.append(websocket)
            logger.debug("WS connected to global feed")

    def disconnect(self, websocket: WebSocket, campaign_id: str = ""):
        if campaign_id and campaign_id in self._connections:
            self._connections[campaign_id] = [
                ws for ws in self._connections[campaign_id] if ws != websocket
            ]
            if not self._connections[campaign_id]:
                del self._connections[campaign_id]
        else:
            self._global = [ws for ws in self._global if ws != websocket]

    async def broadcast_to_campaign(self, campaign_id: str, event: dict):
        """Push event to all connections watching a specific campaign."""
        event["timestamp"] = datetime.utcnow().isoformat()
        message = json.dumps(event)

        # Send to campaign-specific connections
        dead = []
        for ws in self._connections.get(campaign_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, campaign_id)

        # Also send to global connections
        await self._broadcast_global(event)

    async def _broadcast_global(self, event: dict):
        """Push event to all global (portfolio) connections."""
        message = json.dumps(event)
        dead = []
        for ws in self._global:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_agent_status(self, campaign_id: str, agent_id: str,
                                status: str, **kwargs):
        """Convenience: push agent status change."""
        await self.broadcast_to_campaign(campaign_id, {
            "type": "agent_status",
            "agent_id": agent_id,
            "status": status,
            **kwargs,
        })

    async def send_metric_update(self, campaign_id: str, metric_type: str,
                                 data: dict):
        """Convenience: push metric update."""
        await self.broadcast_to_campaign(campaign_id, {
            "type": "metric_update",
            "metric_type": metric_type,
            "data": data,
        })

    async def send_score_update(self, campaign_id: str, scores: dict):
        """Convenience: push score refresh."""
        await self.broadcast_to_campaign(campaign_id, {
            "type": "score_update",
            "scores": scores,
        })

    async def send_trigger_fired(self, campaign_id: str, trigger: dict):
        """Convenience: push sensing trigger event."""
        await self.broadcast_to_campaign(campaign_id, {
            "type": "trigger_fired",
            "trigger": trigger,
        })

    async def send_approval_needed(self, campaign_id: str, approval: dict):
        """Convenience: push approval request."""
        await self.broadcast_to_campaign(campaign_id, {
            "type": "approval_needed",
            "approval": approval,
        })

    @property
    def connection_count(self) -> int:
        campaign_count = sum(len(conns) for conns in self._connections.values())
        return campaign_count + len(self._global)

    def get_status(self) -> dict:
        return {
            "total_connections": self.connection_count,
            "campaign_connections": {k: len(v) for k, v in self._connections.items()},
            "global_connections": len(self._global),
        }


# Singleton
ws_manager = ConnectionManager()
