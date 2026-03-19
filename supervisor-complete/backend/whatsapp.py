"""
Supervisor Backend — WhatsApp Business Integration
Full WhatsApp Cloud API integration for agent-to-user communication.
Competes with OpenClaw & Manus WhatsApp-first interfaces.
"""
from __future__ import annotations
import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger("supervisor.whatsapp")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsAppMessage:
    """Represents an inbound or outbound WhatsApp message."""
    def __init__(self, phone: str, text: str = "", direction: str = "inbound",
                 message_type: str = "text", media_url: str = "",
                 template_name: str = "", template_params: list = None):
        self.phone = phone
        self.text = text
        self.direction = direction
        self.message_type = message_type  # text | template | interactive | media
        self.media_url = media_url
        self.template_name = template_name
        self.template_params = template_params or []
        self.timestamp = datetime.utcnow()
        self.wa_message_id: str = ""
        self.status: str = "pending"  # pending | sent | delivered | read | failed


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP CLOUD API CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsAppClient:
    """
    WhatsApp Business Cloud API client.
    Handles sending messages, templates, interactive buttons, and media.
    Receives webhooks for inbound messages and delivery receipts.
    """

    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.access_token = getattr(settings, "whatsapp_access_token", "")
        self.phone_number_id = getattr(settings, "whatsapp_phone_number_id", "")
        self.verify_token = getattr(settings, "whatsapp_verify_token", "supervisor_wa_verify")
        self.app_secret = getattr(settings, "whatsapp_app_secret", "")
        self._client = httpx.AsyncClient(timeout=30)
        self._conversations: dict[str, list[WhatsAppMessage]] = {}  # phone -> messages
        self._command_handlers: dict[str, Any] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ── Outbound Messages ────────────────────────────────────────────────────

    async def send_text(self, phone: str, text: str) -> dict:
        """Send a plain text message."""
        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }
        return await self._send(phone, body, text)

    async def send_template(self, phone: str, template_name: str,
                            language: str = "en_US",
                            parameters: list[str] = None) -> dict:
        """Send a pre-approved template message (required for initiating conversations)."""
        components = []
        if parameters:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in parameters],
            })

        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }
        return await self._send(phone, body, f"[template:{template_name}]")

    async def send_interactive_buttons(self, phone: str, body_text: str,
                                       buttons: list[dict]) -> dict:
        """
        Send interactive button message.
        buttons: [{"id": "btn_1", "title": "Approve"}, ...]
        """
        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                        for b in buttons[:3]  # WhatsApp max 3 buttons
                    ],
                },
            },
        }
        return await self._send(phone, body, body_text)

    async def send_interactive_list(self, phone: str, body_text: str,
                                    button_text: str, sections: list[dict]) -> dict:
        """
        Send interactive list message.
        sections: [{"title": "Options", "rows": [{"id": "1", "title": "Option 1", "description": "..."}]}]
        """
        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {
                    "button": button_text[:20],
                    "sections": sections,
                },
            },
        }
        return await self._send(phone, body, body_text)

    async def send_media(self, phone: str, media_type: str, media_url: str,
                         caption: str = "") -> dict:
        """Send image, video, or document."""
        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": media_type,  # image | video | document | audio
            media_type: {"link": media_url},
        }
        if caption and media_type in ("image", "video", "document"):
            body[media_type]["caption"] = caption
        return await self._send(phone, body, f"[{media_type}:{caption}]")

    async def _send(self, phone: str, body: dict, text: str) -> dict:
        """Execute the API call and log the message."""
        msg = WhatsAppMessage(phone=phone, text=text, direction="outbound",
                              message_type=body.get("type", "text"))

        if not self.is_configured:
            msg.status = "simulated"
            self._log_message(msg)
            logger.info(f"[WhatsApp SIM] → {phone}: {text[:100]}")
            return {"simulated": True, "phone": phone, "text": text}

        try:
            resp = await self._client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers=self._headers(), json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            msg.wa_message_id = data.get("messages", [{}])[0].get("id", "")
            msg.status = "sent"
            self._log_message(msg)
            logger.info(f"[WhatsApp] → {phone}: {text[:100]}")
            return data
        except Exception as e:
            msg.status = "failed"
            self._log_message(msg)
            logger.error(f"WhatsApp send failed: {e}")
            return {"error": str(e)}

    # ── Inbound Webhook ──────────────────────────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Meta webhook signature."""
        if not self.app_secret:
            return True  # Skip verification in dev
        expected = hmac.new(
            self.app_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    def parse_webhook(self, data: dict) -> list[WhatsAppMessage]:
        """Parse inbound webhook payload into messages."""
        messages = []
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Status updates (delivery receipts)
                for status in value.get("statuses", []):
                    self._handle_status_update(status)

                # Inbound messages
                for msg_data in value.get("messages", []):
                    msg = self._parse_message(msg_data, value.get("contacts", []))
                    if msg:
                        messages.append(msg)
                        self._log_message(msg)
        return messages

    def _parse_message(self, msg_data: dict, contacts: list) -> Optional[WhatsAppMessage]:
        """Parse a single inbound message."""
        phone = msg_data.get("from", "")
        msg_type = msg_data.get("type", "text")

        text = ""
        if msg_type == "text":
            text = msg_data.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = msg_data.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("id", "")
            elif interactive.get("type") == "list_reply":
                text = interactive.get("list_reply", {}).get("id", "")
        elif msg_type == "image":
            text = msg_data.get("image", {}).get("caption", "[image]")

        msg = WhatsAppMessage(
            phone=phone, text=text, direction="inbound",
            message_type=msg_type,
        )
        msg.wa_message_id = msg_data.get("id", "")
        msg.status = "received"
        return msg

    def _handle_status_update(self, status: dict):
        """Handle delivery receipt updates."""
        # Could update message status in DB
        logger.debug(f"WhatsApp status: {status.get('id')} → {status.get('status')}")

    def _log_message(self, msg: WhatsAppMessage):
        """Log message to conversation history."""
        if msg.phone not in self._conversations:
            self._conversations[msg.phone] = []
        self._conversations[msg.phone].append(msg)

    # ── Command Processing ───────────────────────────────────────────────────

    def register_command(self, command: str, handler):
        """Register a command handler (e.g., /status, /briefing)."""
        self._command_handlers[command.lower()] = handler

    async def process_inbound(self, msg: WhatsAppMessage) -> Optional[str]:
        """
        Process an inbound message:
        - Check for commands (/status, /briefing, etc.)
        - Route to LLM for natural language
        - Return response text
        """
        text = msg.text.strip()

        # Check for commands
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            handler = self._command_handlers.get(cmd)
            if handler:
                return await handler(msg.phone, args) if callable(handler) else str(handler)
            return f"Unknown command: {cmd}\n\nAvailable: {', '.join(self._command_handlers.keys())}"

        # Natural language — route to Supervisor
        return None  # Caller should route to LLM

    # ── Proactive Outbound ───────────────────────────────────────────────────

    async def send_daily_briefing(self, phone: str, briefing: dict):
        """Send a formatted daily briefing."""
        lines = ["*Daily Briefing*\n"]

        if briefing.get("revenue"):
            lines.append(f"Revenue: ${briefing['revenue']:,.2f}")
        if briefing.get("leads"):
            lines.append(f"New leads: {briefing['leads']}")
        if briefing.get("emails_sent"):
            lines.append(f"Emails sent: {briefing['emails_sent']}")
        if briefing.get("reply_rate"):
            lines.append(f"Reply rate: {briefing['reply_rate']:.1f}%")
        if briefing.get("ad_spend"):
            lines.append(f"Ad spend: ${briefing['ad_spend']:,.2f}")
        if briefing.get("roas"):
            lines.append(f"ROAS: {briefing['roas']:.1f}x")

        if briefing.get("alerts"):
            lines.append("\n*Alerts:*")
            for alert in briefing["alerts"][:5]:
                lines.append(f"  - {alert}")

        if briefing.get("pending_approvals"):
            lines.append(f"\n*{briefing['pending_approvals']} approvals pending*")

        text = "\n".join(lines)
        return await self.send_text(phone, text)

    async def send_approval_request(self, phone: str, approval: dict):
        """Send an interactive approval request with buttons."""
        text = (
            f"*Approval Required*\n\n"
            f"Agent: {approval.get('agent', 'Unknown')}\n"
            f"Action: {approval.get('action', 'Unknown')}\n"
            f"Details: {approval.get('details', '')}\n"
            f"Cost: ${approval.get('cost', 0):,.2f}"
        )
        buttons = [
            {"id": f"approve_{approval.get('id', '')}", "title": "Approve"},
            {"id": f"reject_{approval.get('id', '')}", "title": "Reject"},
            {"id": f"details_{approval.get('id', '')}", "title": "Details"},
        ]
        return await self.send_interactive_buttons(phone, text, buttons)

    async def send_alert(self, phone: str, alert_type: str, message: str):
        """Send a priority alert."""
        prefix = {
            "revenue": "[REVENUE]", "error": "[ERROR]", "milestone": "[MILESTONE]",
            "threshold": "[THRESHOLD]", "opportunity": "[OPPORTUNITY]",
        }.get(alert_type, "[ALERT]")
        return await self.send_text(phone, f"{prefix} *{alert_type.upper()}*\n\n{message}")

    def get_conversation(self, phone: str, limit: int = 50) -> list[dict]:
        """Get conversation history for a phone number."""
        msgs = self._conversations.get(phone, [])[-limit:]
        return [
            {
                "phone": m.phone, "text": m.text, "direction": m.direction,
                "type": m.message_type, "status": m.status,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in msgs
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

whatsapp = WhatsAppClient()
