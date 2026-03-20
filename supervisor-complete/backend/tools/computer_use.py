"""
Live browser sessions, browser actions, vision navigation, parallel browsers, and handoffs.
"""

from __future__ import annotations

import json


async def _launch_live_browser(agent_id: str, start_url: str = "", campaign_id: str = "",
                                viewport_width: str = "1440", viewport_height: str = "900",
                                proxy: str = "", recording: str = "true") -> str:
    """Launch a live browser session with real-time streaming for an agent."""
    from computer_use import browser_pool
    session = await browser_pool.create_session(
        agent_id=agent_id, campaign_id=campaign_id, start_url=start_url,
        viewport={"width": int(viewport_width), "height": int(viewport_height)},
        proxy=proxy, recording=recording.lower() == "true",
    )
    return json.dumps(session.to_dict())



async def _browser_action(session_id: str, action_type: str, selector: str = "",
                           value: str = "", coordinates: str = "",
                           description: str = "") -> str:
    """Execute a browser action (click, type, navigate, scroll, etc.) in a live session."""
    from computer_use import browser_pool, BrowserAction, ActionType
    coords = None
    if coordinates:
        parts = [int(x.strip()) for x in coordinates.split(",")]
        coords = (parts[0], parts[1]) if len(parts) == 2 else None
    action = BrowserAction(
        action_type=ActionType(action_type), selector=selector,
        value=value, coordinates=coords, description=description,
    )
    result = await browser_pool.execute_action(session_id, action)
    return json.dumps(result)



async def _vision_navigate(session_id: str, goal: str, screenshot_b64: str = "") -> str:
    """Vision-guided browser navigation — screenshot → LLM vision → next action."""
    from computer_use import browser_pool
    result = await browser_pool.vision_step(session_id, goal, screenshot_b64)
    return json.dumps(result)



async def _vision_plan(session_id: str, goal: str, screenshot_b64: str = "",
                        max_steps: str = "20") -> str:
    """Plan a full multi-step browser interaction sequence using vision analysis."""
    from computer_use import browser_pool
    session = browser_pool._sessions.get(session_id)
    if not session:
        return json.dumps({"error": f"Session {session_id} not found"})
    plan = await browser_pool._vision.plan_multi_step(screenshot_b64, goal, int(max_steps))
    return json.dumps({"session_id": session_id, "plan": plan})



async def _browser_parallel_launch(tasks_json: str) -> str:
    """Launch multiple browser sessions in parallel — N agents, N browsers, simultaneously."""
    from computer_use import browser_pool
    tasks = json.loads(tasks_json)
    result = await browser_pool.run_parallel_sessions(tasks)
    return json.dumps(result)



async def _browser_request_handoff(session_id: str, reason: str,
                                    notify_channels: str = "telegram,slack,whatsapp") -> str:
    """Agent yields browser control to human."""
    from computer_use import browser_pool
    channels = [c.strip() for c in notify_channels.split(",")]
    result = await browser_pool.request_human_handoff(session_id, reason, channels)
    return json.dumps(result)



async def _browser_close_session(session_id: str) -> str:
    """Close a browser session and finalize its recording."""
    from computer_use import browser_pool
    result = await browser_pool.close_session(session_id)
    return json.dumps(result)



async def _browser_get_dashboard() -> str:
    """Get the multi-browser dashboard."""
    from computer_use import browser_pool
    return json.dumps(browser_pool.get_dashboard())



async def _browser_get_recording(recording_id: str, format: str = "json") -> str:
    """Get or export a browser session recording."""
    from computer_use import browser_pool
    result = await browser_pool.export_recording(recording_id, format)
    return json.dumps(result)



async def _browser_annotate_recording(recording_id: str, frame_index: str,
                                       annotation: str) -> str:
    """Add human annotation to a specific frame in a browser recording."""
    from computer_use import browser_pool
    result = await browser_pool.annotate_recording(recording_id, int(frame_index), annotation)
    return json.dumps(result)



async def _browser_get_stats() -> str:
    """Get aggregate statistics across all browser sessions."""
    from computer_use import browser_pool
    return json.dumps(browser_pool.get_stats())



def register_computer_use_tools(registry):
    """Register all computer_use tools with the given registry."""
    from models import ToolParameter

    registry.register("launch_live_browser", "Launch a live browser session with real-time streaming. Users can watch the agent browse in real-time via WebSocket stream.",
        [ToolParameter(name="agent_id", description="Agent requesting the browser"),
         ToolParameter(name="start_url", description="Initial URL to navigate to", required=False),
         ToolParameter(name="campaign_id", description="Campaign context", required=False),
         ToolParameter(name="viewport_width", description="Browser viewport width in pixels (default 1440)", required=False),
         ToolParameter(name="viewport_height", description="Browser viewport height in pixels (default 900)", required=False),
         ToolParameter(name="proxy", description="Proxy URL for the browser session", required=False),
         ToolParameter(name="recording", description="Enable session recording (default true)", required=False)],
        _launch_live_browser, "computer_use")

    registry.register("browser_action", "Execute a browser action in a live session — click, type, navigate, scroll, select, hover, upload, drag, key press. All actions are streamed to viewers in real-time.",
        [ToolParameter(name="session_id", description="Browser session ID"),
         ToolParameter(name="action_type", description="Action: navigate, click, type, scroll, select, hover, upload, wait, extract, execute_js, drag_drop, key_press"),
         ToolParameter(name="selector", description="CSS or XPath selector for the target element", required=False),
         ToolParameter(name="value", description="URL for navigate, text for type, key for key_press", required=False),
         ToolParameter(name="coordinates", description="Pixel coordinates 'x,y' for vision-guided clicks", required=False),
         ToolParameter(name="description", description="Human-readable explanation of this action", required=False)],
        _browser_action, "computer_use")

    registry.register("vision_navigate", "Vision-guided browser step — sends screenshot to vision model, gets back recommended action. Works on ANY site including anti-bot, canvas UIs, and SPAs.",
        [ToolParameter(name="session_id", description="Browser session ID"),
         ToolParameter(name="goal", description="What the agent is trying to accomplish on this page"),
         ToolParameter(name="screenshot_b64", description="Base64 screenshot of current browser state", required=False)],
        _vision_navigate, "computer_use")

    registry.register("vision_plan", "Plan a full multi-step browser interaction using vision analysis. Vision model sees current state and produces step-by-step plan with fallbacks.",
        [ToolParameter(name="session_id", description="Browser session ID"),
         ToolParameter(name="goal", description="Complex goal to plan steps for"),
         ToolParameter(name="screenshot_b64", description="Base64 screenshot of current browser state", required=False),
         ToolParameter(name="max_steps", description="Maximum steps in the plan (default 20)", required=False)],
        _vision_plan, "computer_use")

    registry.register("browser_parallel_launch", "Launch multiple browser sessions simultaneously — N agents, N browsers, all streaming live. THE differentiator vs single-browser competitors.",
        [ToolParameter(name="tasks_json", description="JSON array of tasks: [{agent_id, campaign_id, goal, start_url}, ...]")],
        _browser_parallel_launch, "computer_use")

    registry.register("browser_request_handoff", "Agent yields browser control to human when stuck (captcha, login, ambiguous choice). Sends notification via Telegram/Slack/WhatsApp with live stream link.",
        [ToolParameter(name="session_id", description="Browser session ID"),
         ToolParameter(name="reason", description="Why the agent needs human help"),
         ToolParameter(name="notify_channels", description="Comma-separated channels: telegram,slack,whatsapp (default all)", required=False)],
        _browser_request_handoff, "computer_use")

    registry.register("browser_close_session", "Close a browser session and finalize its recording.",
        [ToolParameter(name="session_id", description="Browser session ID to close")],
        _browser_close_session, "computer_use")

    registry.register("browser_dashboard", "Get the multi-browser control panel — all active sessions, live stream URLs, stats, and available slots.",
        [], _browser_get_dashboard, "computer_use")

    registry.register("browser_get_recording", "Get or export a browser session recording with full action timeline, decision points, and annotations. Formats: json, html_replay, mp4.",
        [ToolParameter(name="recording_id", description="Recording ID to retrieve"),
         ToolParameter(name="format", description="Export format: json, html_replay, mp4 (default json)", required=False)],
        _browser_get_recording, "computer_use")

    registry.register("browser_annotate_recording", "Add human annotation to a specific frame in a browser session recording.",
        [ToolParameter(name="recording_id", description="Recording ID"),
         ToolParameter(name="frame_index", description="Frame number to annotate (0-indexed)"),
         ToolParameter(name="annotation", description="Annotation text")],
        _browser_annotate_recording, "computer_use")

    registry.register("browser_stats", "Get aggregate statistics across all browser sessions — actions, domains, handoffs, concurrency peaks.",
        [], _browser_get_stats, "computer_use")

    # ── Hardware Manufacturing Tools ──────────────────────────────────────────

