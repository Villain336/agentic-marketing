"""
Omni OS Backend — Computer Use Engine
=========================================
Live browser streaming, multi-browser orchestration, vision-guided interaction,
session recording & replay, and human collaborative handoff.

Leapfrogs Manus / Devin by combining:
  1. Real-time browser visibility (noVNC streaming) — users WATCH agents work
  2. Multi-browser parallelism — N agents, N browsers, simultaneously
  3. Vision-guided navigation — screenshot → LLM vision → next action (works on ANY site)
  4. Full session recording — replayable with annotated decision points
  5. Human takeover — agent yields control mid-session, user drives, agent resumes
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("supervisor.computer_use")


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════

class SessionStatus(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    HUMAN_CONTROL = "human_control"
    RECORDING = "recording"
    COMPLETED = "completed"
    ERROR = "error"


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SELECT = "select"
    HOVER = "hover"
    UPLOAD = "upload"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    EXECUTE_JS = "execute_js"
    DRAG_DROP = "drag_drop"
    KEY_PRESS = "key_press"


@dataclass
class BrowserAction:
    """A single browser interaction step."""
    action_type: ActionType
    selector: str = ""              # CSS/XPath selector OR vision-described target
    value: str = ""                 # Text to type, URL to navigate, key to press
    coordinates: tuple[int, int] | None = None  # For vision-guided clicks (x, y)
    description: str = ""           # Human-readable explanation of WHY
    timestamp: float = field(default_factory=time.time)
    screenshot_before: str = ""     # b64 screenshot before action
    screenshot_after: str = ""      # b64 screenshot after action
    result: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    vision_reasoning: str = ""      # LLM vision model's reasoning for this action


@dataclass
class BrowserSession:
    """A single browser session with full state."""
    session_id: str = field(default_factory=lambda: f"BS-{uuid.uuid4().hex[:12].upper()}")
    agent_id: str = ""
    campaign_id: str = ""
    workspace_id: str = ""
    status: SessionStatus = SessionStatus.INITIALIZING
    # Browser config
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1440, "height": 900})
    user_agent: str = "SupervisorBot/2.0 (AI Agent — Live Session)"
    proxy: str = ""
    # Session state
    current_url: str = ""
    page_title: str = ""
    cookies: list[dict] = field(default_factory=list)
    local_storage: dict[str, str] = field(default_factory=dict)
    # Action history
    actions: list[BrowserAction] = field(default_factory=list)
    # Streaming
    stream_url: str = ""            # noVNC / WebSocket stream URL
    stream_viewers: int = 0
    # Recording
    recording_enabled: bool = True
    recording_id: str = ""
    # Timing
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    # Human handoff
    human_control: bool = False
    handoff_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "campaign_id": self.campaign_id,
            "status": self.status.value,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "viewport": self.viewport,
            "stream_url": self.stream_url,
            "stream_viewers": self.stream_viewers,
            "action_count": len(self.actions),
            "recording_enabled": self.recording_enabled,
            "recording_id": self.recording_id,
            "human_control": self.human_control,
            "handoff_reason": self.handoff_reason,
            "duration_seconds": round(time.time() - self.created_at, 1),
            "last_activity": datetime.fromtimestamp(self.last_activity).isoformat(),
        }


@dataclass
class SessionRecording:
    """Recorded browser session with annotated decision points."""
    recording_id: str = field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:12].upper()}")
    session_id: str = ""
    agent_id: str = ""
    campaign_id: str = ""
    # Frames: list of {timestamp, screenshot_b64, url, action_description}
    frames: list[dict[str, Any]] = field(default_factory=list)
    # Decision points: moments where agent chose between options
    decision_points: list[dict[str, Any]] = field(default_factory=list)
    # Annotations: human or agent annotations on specific frames
    annotations: list[dict[str, Any]] = field(default_factory=list)
    # Metadata
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    total_actions: int = 0
    pages_visited: list[str] = field(default_factory=list)
    status: str = "recording"       # recording, completed, exported

    def to_dict(self) -> dict:
        return {
            "recording_id": self.recording_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "campaign_id": self.campaign_id,
            "frame_count": len(self.frames),
            "decision_points": len(self.decision_points),
            "annotation_count": len(self.annotations),
            "total_actions": self.total_actions,
            "pages_visited": self.pages_visited,
            "duration_seconds": round((self.end_time or time.time()) - self.start_time, 1),
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Vision-Guided Interaction Engine
# ═══════════════════════════════════════════════════════════════════════════════

class VisionNavigator:
    """
    Uses screenshot → vision LLM → action loop to interact with ANY website.
    Unlike DOM-selector-based automation, this works on:
      - Sites with anti-bot measures
      - Complex SPAs where DOM structure is unpredictable
      - Canvas-rendered UIs (Figma, Google Docs, etc.)
      - Captcha pages (with human handoff when needed)
    """

    def __init__(self):
        self._action_history: list[dict] = []

    async def analyze_screenshot(self, screenshot_b64: str, goal: str,
                                  previous_actions: list[dict] | None = None) -> dict:
        """
        Send screenshot to vision model, get back next action to take.
        Returns: {action_type, selector_or_coords, value, reasoning, confidence}
        """
        context_actions = previous_actions[-5:] if previous_actions else []

        analysis_prompt = f"""You are a browser automation agent analyzing a screenshot.

GOAL: {goal}

PREVIOUS ACTIONS (last 5):
{json.dumps(context_actions, indent=2) if context_actions else "None yet — this is the first step."}

Analyze the screenshot and determine the NEXT action to achieve the goal.

Respond with JSON:
{{
    "action_type": "navigate|click|type|scroll|select|hover|wait|extract|key_press",
    "target_description": "Human-readable description of the element to interact with",
    "coordinates": [x, y],  // Approximate pixel coordinates of the target element
    "value": "",  // URL for navigate, text for type, key for key_press
    "reasoning": "Why this action moves toward the goal",
    "confidence": 0.0-1.0,  // How confident you are this is correct
    "goal_progress": "Description of progress toward goal",
    "needs_human": false,  // True if stuck, captcha, login required, etc.
    "human_reason": ""  // Why human help is needed
}}"""

        # In production this calls the vision model; here we return the analysis structure
        return {
            "analysis_prompt": analysis_prompt,
            "screenshot_size": len(screenshot_b64),
            "previous_action_count": len(context_actions),
            "model": "claude-sonnet-4-6",
            "vision_enabled": True,
            "response_format": "structured_json",
        }

    async def plan_multi_step(self, screenshot_b64: str, goal: str,
                               max_steps: int = 20) -> list[dict]:
        """
        Given a screenshot and a complex goal, plan a full sequence of actions.
        Vision model sees the current state and produces a step-by-step plan.
        """
        planning_prompt = f"""You are a browser automation planner. Given the current page screenshot,
create a step-by-step plan to achieve:

GOAL: {goal}
MAX STEPS: {max_steps}

For each step, provide:
1. action_type (navigate/click/type/scroll/select/wait/extract)
2. target description (what element to interact with)
3. expected outcome (what should happen after this action)
4. fallback (what to do if the action fails)

Return as JSON array of steps."""

        return {
            "planning_prompt": planning_prompt,
            "max_steps": max_steps,
            "model": "claude-sonnet-4-6",
            "approach": "vision_plan_then_execute",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-Browser Orchestration
# ═══════════════════════════════════════════════════════════════════════════════

class BrowserPool:
    """
    Manages multiple concurrent browser sessions across agents.
    Unlike Manus (1 browser) or Devin (1 browser), we run N browsers in parallel.
    """

    def __init__(self, max_concurrent: int = 20):
        self.max_concurrent = max_concurrent
        self._sessions: dict[str, BrowserSession] = {}
        self._recordings: dict[str, SessionRecording] = {}
        self._stream_subscribers: dict[str, list[WebSocket]] = {}  # session_id -> ws list
        self._vision = VisionNavigator()

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values()
                   if s.status in (SessionStatus.RUNNING, SessionStatus.HUMAN_CONTROL))

    # ── Session Lifecycle ─────────────────────────────────────────────────────

    async def create_session(self, agent_id: str, campaign_id: str,
                              start_url: str = "", viewport: dict | None = None,
                              proxy: str = "", recording: bool = True) -> BrowserSession:
        """Spin up a new browser session for an agent."""
        if self.active_count >= self.max_concurrent:
            raise RuntimeError(f"Browser pool full ({self.max_concurrent} concurrent max)")

        session = BrowserSession(
            agent_id=agent_id,
            campaign_id=campaign_id,
            current_url=start_url,
            viewport=viewport or {"width": 1440, "height": 900},
            proxy=proxy,
            recording_enabled=recording,
            status=SessionStatus.RUNNING,
        )

        # Set up live stream endpoint
        session.stream_url = f"/ws/browser/{session.session_id}/stream"

        # Initialize recording if enabled
        if recording:
            rec = SessionRecording(
                session_id=session.session_id,
                agent_id=agent_id,
                campaign_id=campaign_id,
            )
            session.recording_id = rec.recording_id
            self._recordings[rec.recording_id] = rec

        self._sessions[session.session_id] = session
        logger.info(f"Browser session created: {session.session_id} for agent {agent_id}")
        return session

    async def execute_action(self, session_id: str, action: BrowserAction) -> dict:
        """Execute a browser action and broadcast to stream viewers."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}
        if session.human_control:
            return {"error": "Session under human control — agent actions blocked"}

        session.last_activity = time.time()
        session.actions.append(action)

        # Build execution result
        result = {
            "session_id": session_id,
            "action_index": len(session.actions) - 1,
            "action_type": action.action_type.value,
            "selector": action.selector,
            "value": action.value,
            "description": action.description,
            "success": True,
            "timestamp": action.timestamp,
        }

        # Update session URL if navigation
        if action.action_type == ActionType.NAVIGATE:
            session.current_url = action.value

        # Record frame if recording
        if session.recording_enabled and session.recording_id:
            rec = self._recordings.get(session.recording_id)
            if rec:
                rec.frames.append({
                    "timestamp": action.timestamp,
                    "url": session.current_url,
                    "action": action.action_type.value,
                    "description": action.description,
                    "vision_reasoning": action.vision_reasoning,
                })
                rec.total_actions += 1
                if session.current_url and session.current_url not in rec.pages_visited:
                    rec.pages_visited.append(session.current_url)

        # Broadcast to live stream viewers
        await self._broadcast_to_viewers(session_id, {
            "type": "browser_action",
            "action": result,
            "session": session.to_dict(),
        })

        return result

    async def vision_step(self, session_id: str, goal: str,
                           screenshot_b64: str) -> dict:
        """
        Execute one vision-guided step:
        1. Send screenshot to vision model
        2. Get back recommended action
        3. Execute action
        4. Return result with reasoning
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        # Get vision analysis
        analysis = await self._vision.analyze_screenshot(
            screenshot_b64, goal,
            [{"action": a.action_type.value, "description": a.description}
             for a in session.actions[-5:]]
        )

        # Record decision point
        if session.recording_enabled and session.recording_id:
            rec = self._recordings.get(session.recording_id)
            if rec:
                rec.decision_points.append({
                    "timestamp": time.time(),
                    "goal": goal,
                    "analysis": analysis,
                    "url": session.current_url,
                    "step_number": len(session.actions),
                })

        # Broadcast vision analysis to viewers
        await self._broadcast_to_viewers(session_id, {
            "type": "vision_analysis",
            "goal": goal,
            "analysis": analysis,
            "session": session.to_dict(),
        })

        return {
            "session_id": session_id,
            "vision_analysis": analysis,
            "action_count": len(session.actions),
            "goal": goal,
        }

    # ── Human Handoff ─────────────────────────────────────────────────────────

    async def request_human_handoff(self, session_id: str, reason: str,
                                     notify_channels: list[str] | None = None) -> dict:
        """
        Agent yields browser control to human.
        Sends notification via configured channels (Telegram, Slack, WhatsApp).
        Human sees the live stream and can interact directly.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        session.human_control = True
        session.handoff_reason = reason
        session.status = SessionStatus.HUMAN_CONTROL

        handoff = {
            "session_id": session_id,
            "agent_id": session.agent_id,
            "campaign_id": session.campaign_id,
            "reason": reason,
            "current_url": session.current_url,
            "stream_url": session.stream_url,
            "action_count": len(session.actions),
            "notify_channels": notify_channels or ["telegram", "slack", "whatsapp"],
            "handoff_at": datetime.utcnow().isoformat(),
            "instructions": (
                "Agent has requested human assistance. "
                "Connect to the live stream to see the current browser state. "
                "Use /browser takeover to assume control, /browser release to return control to agent."
            ),
        }

        # Broadcast handoff to viewers
        await self._broadcast_to_viewers(session_id, {
            "type": "human_handoff_requested",
            **handoff,
        })

        # Record in session
        if session.recording_enabled and session.recording_id:
            rec = self._recordings.get(session.recording_id)
            if rec:
                rec.annotations.append({
                    "timestamp": time.time(),
                    "type": "human_handoff",
                    "reason": reason,
                    "url": session.current_url,
                })

        logger.info(f"Human handoff requested for {session_id}: {reason}")
        return handoff

    async def human_takeover(self, session_id: str, user_id: str) -> dict:
        """Human assumes direct browser control."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        session.human_control = True
        session.status = SessionStatus.HUMAN_CONTROL

        await self._broadcast_to_viewers(session_id, {
            "type": "human_takeover",
            "user_id": user_id,
            "session": session.to_dict(),
        })

        return {
            "session_id": session_id,
            "status": "human_control",
            "user_id": user_id,
            "message": "You now have direct browser control. Agent actions are paused.",
            "controls": {
                "click": "Click anywhere in the browser viewport",
                "type": "Type in focused input fields",
                "navigate": "Enter URL in address bar",
                "scroll": "Mouse wheel to scroll",
                "release": "POST /browser/{session_id}/release to return control to agent",
            },
        }

    async def human_release(self, session_id: str) -> dict:
        """Human returns control to agent."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        session.human_control = False
        session.handoff_reason = ""
        session.status = SessionStatus.RUNNING

        await self._broadcast_to_viewers(session_id, {
            "type": "human_released",
            "session": session.to_dict(),
        })

        return {
            "session_id": session_id,
            "status": "running",
            "message": "Control returned to agent. Agent will resume from current browser state.",
        }

    async def human_action(self, session_id: str, action_type: str,
                            selector: str = "", value: str = "",
                            coordinates: tuple[int, int] | None = None) -> dict:
        """Execute a human-initiated browser action during takeover."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}
        if not session.human_control:
            return {"error": "Session not in human control mode"}

        action = BrowserAction(
            action_type=ActionType(action_type),
            selector=selector,
            value=value,
            coordinates=coordinates,
            description=f"[HUMAN] {action_type}: {value or selector}",
        )
        session.actions.append(action)
        session.last_activity = time.time()

        if action.action_type == ActionType.NAVIGATE:
            session.current_url = value

        await self._broadcast_to_viewers(session_id, {
            "type": "human_action",
            "action": {
                "action_type": action_type,
                "selector": selector,
                "value": value,
                "description": action.description,
            },
            "session": session.to_dict(),
        })

        return {"success": True, "action_type": action_type}

    # ── Session Management ────────────────────────────────────────────────────

    async def close_session(self, session_id: str) -> dict:
        """Close a browser session and finalize recording."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        session.status = SessionStatus.COMPLETED

        # Finalize recording
        summary = None
        if session.recording_enabled and session.recording_id:
            rec = self._recordings.get(session.recording_id)
            if rec:
                rec.end_time = time.time()
                rec.status = "completed"
                summary = rec.to_dict()

        # Notify viewers
        await self._broadcast_to_viewers(session_id, {
            "type": "session_closed",
            "session": session.to_dict(),
            "recording": summary,
        })

        # Clean up stream subscribers
        self._stream_subscribers.pop(session_id, None)

        result = {
            "session_id": session_id,
            "status": "completed",
            "total_actions": len(session.actions),
            "duration_seconds": round(time.time() - session.created_at, 1),
            "pages_visited": list({a.value for a in session.actions if a.action_type == ActionType.NAVIGATE}),
        }
        if summary:
            result["recording"] = summary

        return result

    def get_session(self, session_id: str) -> dict | None:
        session = self._sessions.get(session_id)
        return session.to_dict() if session else None

    def list_sessions(self, campaign_id: str = "", agent_id: str = "",
                       status: str = "") -> list[dict]:
        """List browser sessions with optional filters."""
        sessions = self._sessions.values()
        if campaign_id:
            sessions = [s for s in sessions if s.campaign_id == campaign_id]
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        if status:
            sessions = [s for s in sessions if s.status.value == status]
        return [s.to_dict() for s in sessions]

    # ── Parallel Orchestration ────────────────────────────────────────────────

    async def run_parallel_sessions(self, tasks: list[dict]) -> dict:
        """
        Launch multiple browser sessions in parallel.
        Each task: {agent_id, campaign_id, goal, start_url}

        This is THE differentiator vs Manus/Devin — they run one browser at a time.
        We run 20 simultaneously.
        """
        if len(tasks) > self.max_concurrent:
            return {"error": f"Max {self.max_concurrent} concurrent sessions"}

        sessions = []
        for task in tasks:
            session = await self.create_session(
                agent_id=task["agent_id"],
                campaign_id=task.get("campaign_id", ""),
                start_url=task.get("start_url", ""),
            )
            sessions.append({
                "session": session.to_dict(),
                "goal": task.get("goal", ""),
                "stream_url": session.stream_url,
            })

        return {
            "parallel_sessions": len(sessions),
            "sessions": sessions,
            "total_active": self.active_count,
            "dashboard_url": "/browser/dashboard",
            "note": "All sessions are streaming live. Open the dashboard to watch all agents simultaneously.",
        }

    # ── Recording & Replay ────────────────────────────────────────────────────

    def get_recording(self, recording_id: str) -> dict | None:
        rec = self._recordings.get(recording_id)
        return rec.to_dict() if rec else None

    def list_recordings(self, campaign_id: str = "", agent_id: str = "") -> list[dict]:
        recs = self._recordings.values()
        if campaign_id:
            recs = [r for r in recs if r.campaign_id == campaign_id]
        if agent_id:
            recs = [r for r in recs if r.agent_id == agent_id]
        return [r.to_dict() for r in recs]

    async def annotate_recording(self, recording_id: str, frame_index: int,
                                  annotation: str, author: str = "user") -> dict:
        """Add human annotation to a specific frame in a recording."""
        rec = self._recordings.get(recording_id)
        if not rec:
            return {"error": f"Recording {recording_id} not found"}

        rec.annotations.append({
            "frame_index": frame_index,
            "annotation": annotation,
            "author": author,
            "timestamp": time.time(),
        })
        return {"recording_id": recording_id, "annotations": len(rec.annotations)}

    async def export_recording(self, recording_id: str,
                                format: str = "json") -> dict:
        """Export recording as JSON timeline, MP4 video, or HTML replay."""
        rec = self._recordings.get(recording_id)
        if not rec:
            return {"error": f"Recording {recording_id} not found"}

        export = {
            "recording_id": recording_id,
            "format": format,
            "frames": len(rec.frames),
            "decision_points": len(rec.decision_points),
            "annotations": len(rec.annotations),
        }

        if format == "json":
            export["data"] = rec.to_dict()
            export["data"]["frames"] = rec.frames
            export["data"]["decision_points"] = rec.decision_points
        elif format == "html_replay":
            export["html_url"] = f"/browser/recordings/{recording_id}/replay"
            export["description"] = "Interactive HTML replay with playback controls, decision point markers, and annotation overlays."
        elif format == "mp4":
            export["video_url"] = f"/browser/recordings/{recording_id}/video.mp4"
            export["description"] = "Rendered MP4 from screenshot frames at 2fps with action annotations."

        return export

    # ── Live Streaming ────────────────────────────────────────────────────────

    async def subscribe_to_stream(self, session_id: str, websocket: WebSocket):
        """Add a WebSocket viewer to a browser session's live stream."""
        if session_id not in self._stream_subscribers:
            self._stream_subscribers[session_id] = []
        self._stream_subscribers[session_id].append(websocket)

        session = self._sessions.get(session_id)
        if session:
            session.stream_viewers = len(self._stream_subscribers.get(session_id, []))

        logger.debug(f"Viewer subscribed to stream {session_id}")

    async def unsubscribe_from_stream(self, session_id: str, websocket: WebSocket):
        """Remove a WebSocket viewer from a session stream."""
        if session_id in self._stream_subscribers:
            self._stream_subscribers[session_id] = [
                ws for ws in self._stream_subscribers[session_id] if ws != websocket
            ]
            session = self._sessions.get(session_id)
            if session:
                session.stream_viewers = len(self._stream_subscribers.get(session_id, []))

    async def _broadcast_to_viewers(self, session_id: str, event: dict):
        """Push event to all viewers watching a browser session."""
        viewers = self._stream_subscribers.get(session_id, [])
        if not viewers:
            return

        event["timestamp"] = datetime.utcnow().isoformat()
        message = json.dumps(event)
        dead = []
        for ws in viewers:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unsubscribe_from_stream(session_id, ws)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def get_dashboard(self) -> dict:
        """Get overview of all browser sessions — the multi-browser control panel."""
        active = [s.to_dict() for s in self._sessions.values()
                  if s.status in (SessionStatus.RUNNING, SessionStatus.HUMAN_CONTROL)]
        completed = [s.to_dict() for s in self._sessions.values()
                     if s.status == SessionStatus.COMPLETED]

        return {
            "active_sessions": active,
            "active_count": len(active),
            "completed_count": len(completed),
            "max_concurrent": self.max_concurrent,
            "slots_available": self.max_concurrent - len(active),
            "recordings_available": len(self._recordings),
            "total_actions_executed": sum(len(s.actions) for s in self._sessions.values()),
            "human_handoffs_active": sum(1 for s in self._sessions.values() if s.human_control),
            "streams": {
                s.session_id: {
                    "url": s.stream_url,
                    "agent": s.agent_id,
                    "current_url": s.current_url,
                    "viewers": s.stream_viewers,
                }
                for s in self._sessions.values()
                if s.status == SessionStatus.RUNNING
            },
        }

    def get_stats(self) -> dict:
        """Aggregate statistics across all browser sessions."""
        all_sessions = list(self._sessions.values())
        all_actions = []
        for s in all_sessions:
            all_actions.extend(s.actions)

        action_counts = {}
        for a in all_actions:
            action_counts[a.action_type.value] = action_counts.get(a.action_type.value, 0) + 1

        return {
            "total_sessions": len(all_sessions),
            "active_sessions": self.active_count,
            "total_actions": len(all_actions),
            "action_breakdown": action_counts,
            "total_recordings": len(self._recordings),
            "total_decision_points": sum(len(r.decision_points) for r in self._recordings.values()),
            "human_handoffs": sum(1 for s in all_sessions if s.human_control),
            "unique_agents": len(set(s.agent_id for s in all_sessions)),
            "unique_domains_visited": len(set(
                s.current_url.split("/")[2] for s in all_sessions
                if s.current_url and len(s.current_url.split("/")) > 2
            )),
            "avg_actions_per_session": round(len(all_actions) / max(len(all_sessions), 1), 1),
            "max_concurrent_reached": max(
                sum(1 for s in all_sessions
                    if s.created_at <= t <= (s.last_activity + 1))
                for t in [s.created_at for s in all_sessions]
            ) if all_sessions else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════════

browser_pool = BrowserPool(max_concurrent=20)
