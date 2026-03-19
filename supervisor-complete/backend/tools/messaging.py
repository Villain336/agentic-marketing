"""
Slack and Telegram messaging.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _send_slack_message(channel: str, message: str, blocks: str = "") -> str:
    """Send message to Slack channel."""
    token = getattr(settings, 'slack_bot_token', '') or ""
    if not token:
        return json.dumps({"error": "Slack not configured. Set SLACK_BOT_TOKEN."})
    try:
        payload: dict[str, Any] = {"channel": channel, "text": message}
        if blocks:
            try:
                payload["blocks"] = json.loads(blocks)
            except json.JSONDecodeError:
                pass
        resp = await _http.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload)
        data = resp.json()
        if data.get("ok"):
            return json.dumps({"sent": True, "channel": channel, "ts": data.get("ts", "")})
        return json.dumps({"sent": False, "error": data.get("error", "unknown")})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _send_telegram_message(chat_id: str, message: str, parse_mode: str = "Markdown") -> str:
    """Send message via Telegram bot."""
    token = getattr(settings, 'telegram_bot_token', '') or ""
    if not token:
        return json.dumps({"error": "Telegram not configured. Set TELEGRAM_BOT_TOKEN."})
    try:
        resp = await _http.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": parse_mode})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"sent": True, "message_id": data.get("result", {}).get("message_id", "")})
        return json.dumps({"error": f"Telegram {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_messaging_tools(registry):
    """Register all messaging tools with the given registry."""
    from models import ToolParameter

    registry.register("send_slack_message", "Send message to a Slack channel.",
        [ToolParameter(name="channel", description="Slack channel (e.g. #general or channel ID)"),
         ToolParameter(name="message", description="Message text"),
         ToolParameter(name="blocks", description="Optional Slack Block Kit JSON", required=False)],
        _send_slack_message, "messaging")

    registry.register("send_telegram_message", "Send message via Telegram bot.",
        [ToolParameter(name="chat_id", description="Telegram chat ID"),
         ToolParameter(name="message", description="Message text"),
         ToolParameter(name="parse_mode", description="Parse mode: Markdown or HTML", required=False)],
        _send_telegram_message, "messaging")

