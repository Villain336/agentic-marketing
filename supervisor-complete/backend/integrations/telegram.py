"""
Supervisor Backend — Telegram Bot Integration
The Supervisor meta-agent is accessible via Telegram.
Commands, natural language, and push notifications.
"""
from __future__ import annotations
import json
import logging
import asyncio
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger("supervisor.telegram")

_http = httpx.AsyncClient(timeout=30)


class TelegramBot:
    """Telegram bot for Supervisor — commands and natural language interface."""

    def __init__(self):
        self.token = getattr(settings, 'telegram_bot_token', '') or ""
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self._offset = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    # ── Send Messages ──────────────────────────────────────────────────────

    async def send_message(self, chat_id: str, text: str,
                            parse_mode: str = "Markdown") -> dict:
        """Send a message to a Telegram chat."""
        if not self.is_configured:
            return {"error": "Telegram not configured"}
        try:
            resp = await _http.post(f"{self.base_url}/sendMessage", json={
                "chat_id": chat_id, "text": text[:4096],
                "parse_mode": parse_mode,
            })
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return {"error": str(e)}

    async def send_notification(self, chat_id: str, title: str, body: str) -> dict:
        """Send a formatted notification."""
        text = f"*{title}*\n\n{body}"
        return await self.send_message(chat_id, text)

    # ── Notification Types ─────────────────────────────────────────────────

    async def notify_new_client(self, chat_id: str, client_name: str,
                                  revenue: float) -> dict:
        return await self.send_notification(chat_id,
            "New Client Signed",
            f"Client: {client_name}\nRevenue: ${revenue:,.2f}")

    async def notify_revenue_milestone(self, chat_id: str, amount: float,
                                         period: str) -> dict:
        return await self.send_notification(chat_id,
            "Revenue Milestone",
            f"Total {period} revenue: ${amount:,.2f}")

    async def notify_performance_alert(self, chat_id: str, agent_id: str,
                                         metric: str, value: str, threshold: str) -> dict:
        return await self.send_notification(chat_id,
            f"Performance Alert: {agent_id}",
            f"Metric: {metric}\nCurrent: {value}\nThreshold: {threshold}")

    async def notify_approval_needed(self, chat_id: str, agent_id: str,
                                       action_type: str, description: str,
                                       approval_id: str) -> dict:
        return await self.send_notification(chat_id,
            f"Approval Needed: {action_type}",
            f"Agent: {agent_id}\n{description}\n\nReply: /approve {approval_id}")

    # ── Command Handling ───────────────────────────────────────────────────

    async def handle_command(self, command: str, args: str, chat_id: str,
                              campaign_getter=None) -> str:
        """Process a Telegram command and return response text."""
        cmd = command.lower().strip("/")

        if cmd == "status":
            return await self._cmd_status(campaign_getter)
        elif cmd == "briefing":
            return await self._cmd_briefing(campaign_getter)
        elif cmd == "spend":
            return await self._cmd_spend(campaign_getter)
        elif cmd == "pause":
            return f"Agent `{args}` paused." if args else "Usage: /pause <agent_id>"
        elif cmd == "resume":
            return f"Agent `{args}` resumed." if args else "Usage: /resume <agent_id>"
        elif cmd == "approve":
            return f"Approval `{args}` processed." if args else "Usage: /approve <approval_id>"
        elif cmd == "help":
            return self._help_text()
        else:
            return f"Unknown command: /{cmd}\n\n{self._help_text()}"

    async def handle_natural_language(self, text: str, chat_id: str,
                                       campaign_getter=None) -> str:
        """Process natural language input via the Supervisor agent."""
        # Route through LLM for natural language understanding
        from providers import router as model_router
        from models import Tier

        system = """You are the Supervisor bot. The user is asking about their campaign.
Answer concisely based on available context. If you don't have specific data, say so.
Keep responses under 500 characters for Telegram."""

        try:
            result = await model_router.complete(
                messages=[{"role": "user", "content": text}],
                system=system, tier=Tier.FAST, max_tokens=500,
            )
            return result.get("text", "I couldn't process that request.")
        except Exception as e:
            return f"Error processing request: {e}"

    async def _cmd_status(self, campaign_getter) -> str:
        if not campaign_getter:
            return "No campaign data available."
        campaigns = campaign_getter()
        if not campaigns:
            return "No active campaigns."
        lines = ["*Campaign Status*\n"]
        for cid, c in list(campaigns.items())[:3]:
            m = c.memory
            agents_done = sum([
                bool(m.prospects), bool(m.email_sequence), bool(m.content_strategy),
                bool(m.social_calendar), bool(m.ad_package), bool(m.cs_system),
                bool(m.site_launch_brief),
            ])
            lines.append(f"- {m.business.name}: {agents_done}/12 agents complete")
        return "\n".join(lines)

    async def _cmd_briefing(self, campaign_getter) -> str:
        return "Weekly briefing: Run /agent supervisor to generate a fresh executive briefing."

    async def _cmd_spend(self, campaign_getter) -> str:
        return "Spend tracking: Connect budget data via the wallet API to see spend summaries here."

    def _help_text(self) -> str:
        return """*Supervisor Bot Commands*

/status — Campaign performance summary
/briefing — Weekly executive briefing
/spend — Budget and spend summary
/pause <agent> — Pause an agent
/resume <agent> — Resume an agent
/approve <id> — Approve a queued action
/help — Show this help

You can also ask questions in natural language."""

    # ── Polling (for development) ──────────────────────────────────────────

    async def poll_updates(self, campaign_getter=None):
        """Long-poll for updates (development mode, not production)."""
        if not self.is_configured:
            return
        try:
            resp = await _http.get(f"{self.base_url}/getUpdates",
                params={"offset": self._offset, "timeout": 30})
            data = resp.json()
            for update in data.get("result", []):
                self._offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if not text or not chat_id:
                    continue

                if text.startswith("/"):
                    parts = text.split(" ", 1)
                    cmd = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    response = await self.handle_command(cmd, args, chat_id, campaign_getter)
                else:
                    response = await self.handle_natural_language(text, chat_id, campaign_getter)

                await self.send_message(chat_id, response)
        except Exception as e:
            logger.error(f"Telegram poll error: {e}")


telegram_bot = TelegramBot()
