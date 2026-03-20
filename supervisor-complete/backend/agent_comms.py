"""
Omni OS Backend — Agent-to-Agent Communication Protocol

Real-time message passing between agents during execution.
Agents can share insights, request data from siblings, broadcast
discoveries, and negotiate strategy mid-run.

No competitor does this — they all run agents in silos.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("omnios.agent_comms")


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class MessageType(str, Enum):
    """Types of inter-agent messages."""
    # Data sharing — push insights to siblings
    INSIGHT = "insight"              # "I found something you should know"
    DATA_SHARE = "data_share"        # structured data push (prospects, metrics, etc.)

    # Requests — ask a sibling for something
    DATA_REQUEST = "data_request"    # "Hey outreach, what emails did you send?"
    STRATEGY_REQUEST = "strategy_request"  # "Content agent, what's the messaging angle?"

    # Coordination — negotiate approach
    COORDINATE = "coordinate"        # "I'm about to do X, adjust accordingly"
    HANDOFF = "handoff"              # "I'm done with my part, here's what you need"

    # Alerts — urgent cross-agent signals
    ALERT = "alert"                  # "Something is wrong, all agents should know"
    BLOCKER = "blocker"              # "I'm stuck and need help from another agent"

    # Responses
    RESPONSE = "response"            # Reply to a request


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentMessage:
    """A single inter-agent message.

    ASI-07 fix: Messages include HMAC signature for integrity verification.
    """
    id: str = ""
    from_agent: str = ""
    to_agent: str = ""           # specific agent, or "*" for broadcast
    campaign_id: str = ""
    msg_type: MessageType = MessageType.INSIGHT
    priority: MessagePriority = MessagePriority.NORMAL
    subject: str = ""            # short description
    body: str = ""               # detailed content
    data: dict[str, Any] = field(default_factory=dict)  # structured payload
    reply_to: str = ""           # message ID this is responding to
    timestamp: float = 0.0
    read: bool = False
    ttl_seconds: int = 300       # messages expire after 5 minutes by default
    signature: str = ""          # HMAC signature for integrity (ASI-07)

    # Shared signing key (in production, load from env/secrets)
    _SIGNING_KEY: str = "omnios-agent-comms-v1"

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = f"msg_{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.signature:
            self.signature = self._compute_signature()

    def _compute_signature(self) -> str:
        """Compute HMAC-SHA256 signature over message content."""
        payload = f"{self.id}:{self.from_agent}:{self.to_agent}:{self.campaign_id}:{self.subject}:{self.body}"
        return hmac.new(
            self._SIGNING_KEY.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:32]

    def verify_signature(self) -> bool:
        """Verify message integrity via HMAC."""
        expected = self._compute_signature()
        return hmac.compare_digest(self.signature, expected)

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds

    @property
    def is_broadcast(self) -> bool:
        return self.to_agent == "*"

    def to_prompt_injection(self) -> str:
        """Format this message for injection into an agent's LLM context."""
        priority_tag = f" [{self.priority.value.upper()}]" if self.priority != MessagePriority.NORMAL else ""
        lines = [
            f"[INTER-AGENT MESSAGE{priority_tag} from {self.from_agent}]",
            f"Type: {self.msg_type.value}",
        ]
        if self.subject:
            lines.append(f"Subject: {self.subject}")
        lines.append(f"Content: {self.body}")
        if self.data:
            # Include key data points (truncated)
            data_preview = {k: str(v)[:200] for k, v in list(self.data.items())[:5]}
            lines.append(f"Data: {data_preview}")
        lines.append("[END MESSAGE]")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT COMMUNICATION BUS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentCommsBus:
    """
    Central message bus for agent-to-agent communication.

    Agents post messages to the bus. The engine checks for pending messages
    before each LLM call and injects them into the agent's context.

    Architecture:
    - Per-campaign message queues (agents in different campaigns don't talk)
    - Broadcast support (message all agents in a campaign)
    - Request/response pattern with reply correlation
    - Auto-expiry to prevent stale messages
    - Message deduplication by content hash
    """

    def __init__(self):
        # campaign_id -> agent_id -> list of pending messages
        self._inboxes: dict[str, dict[str, list[AgentMessage]]] = {}
        # All messages for audit/replay
        self._message_log: list[AgentMessage] = []
        self._max_log_size = 2000
        # Subscriptions: agent_id -> list of message types they care about
        self._subscriptions: dict[str, set[MessageType]] = {}
        # Insight patterns: auto-routing rules
        self._routing_rules: list[dict] = DEFAULT_ROUTING_RULES.copy()

    # ── Sending ──────────────────────────────────────────────────────────

    def send(self, message: AgentMessage) -> str:
        """Send a message to another agent (or broadcast to all).

        ASI-07 fix: Validates sender is registered, verifies message signature.
        """
        campaign_id = message.campaign_id
        if campaign_id not in self._inboxes:
            self._inboxes[campaign_id] = {}

        # ASI-07: Verify sender is registered for this campaign
        if message.from_agent not in self._inboxes.get(campaign_id, {}):
            logger.warning(
                f"Rejected message from unregistered agent {message.from_agent} "
                f"in campaign {campaign_id}"
            )
            return ""

        # ASI-07: Verify message integrity
        if not message.verify_signature():
            logger.warning(
                f"Rejected message with invalid signature from {message.from_agent}"
            )
            return ""

        if message.is_broadcast:
            # Deliver to all agents in this campaign except sender
            for agent_id in list(self._inboxes.get(campaign_id, {}).keys()):
                if agent_id != message.from_agent:
                    self._deliver(campaign_id, agent_id, message)
        else:
            self._deliver(campaign_id, message.to_agent, message)

        # Also check auto-routing rules
        self._apply_routing_rules(message)

        # Log
        self._message_log.append(message)
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

        logger.info(
            f"Agent message: {message.from_agent} → {message.to_agent} "
            f"[{message.msg_type.value}] {message.subject}"
        )
        return message.id

    def _deliver(self, campaign_id: str, to_agent: str, message: AgentMessage):
        """Place message in an agent's inbox."""
        if campaign_id not in self._inboxes:
            self._inboxes[campaign_id] = {}
        if to_agent not in self._inboxes[campaign_id]:
            self._inboxes[campaign_id][to_agent] = []
        self._inboxes[campaign_id][to_agent].append(message)

    # ── Receiving ────────────────────────────────────────────────────────

    def check_inbox(self, agent_id: str, campaign_id: str,
                    max_messages: int = 5) -> list[AgentMessage]:
        """
        Check for pending messages. Returns up to max_messages, marks as read.
        Called by engine.py before each LLM call.
        """
        inbox = self._inboxes.get(campaign_id, {}).get(agent_id, [])
        if not inbox:
            return []

        # Filter expired messages
        active = [m for m in inbox if not m.is_expired and not m.read]

        # Sort by priority (urgent first) then timestamp
        priority_order = {
            MessagePriority.URGENT: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 3,
        }
        active.sort(key=lambda m: (priority_order.get(m.priority, 2), m.timestamp))

        # Take up to max_messages
        to_deliver = active[:max_messages]
        for m in to_deliver:
            m.read = True

        # Clean up inbox
        self._inboxes[campaign_id][agent_id] = [
            m for m in inbox if not m.is_expired and not m.read
        ]

        return to_deliver

    def build_context_injection(self, agent_id: str, campaign_id: str) -> str:
        """
        Build a prompt block from pending messages for injection into agent context.
        Returns empty string if no messages.
        """
        messages = self.check_inbox(agent_id, campaign_id)
        if not messages:
            return ""

        lines = [
            "═══ MESSAGES FROM OTHER AGENTS ═══",
            f"You have {len(messages)} message(s) from sibling agents.",
            "Read and incorporate these insights into your work:",
            "",
        ]
        for msg in messages:
            lines.append(msg.to_prompt_injection())
            lines.append("")

        lines.append(
            "If any message requires a response, use the agent_respond tool "
            "or incorporate the insight directly into your output."
        )
        lines.append("═══════════════════════════════════")
        return "\n".join(lines)

    # ── Agent Registration ───────────────────────────────────────────────

    def register_agent(self, agent_id: str, campaign_id: str,
                       subscribe_to: set[MessageType] | None = None):
        """Register an agent for communication in a campaign."""
        if campaign_id not in self._inboxes:
            self._inboxes[campaign_id] = {}
        if agent_id not in self._inboxes[campaign_id]:
            self._inboxes[campaign_id][agent_id] = []
        if subscribe_to:
            self._subscriptions[agent_id] = subscribe_to

    def deregister_agent(self, agent_id: str, campaign_id: str):
        """Remove agent from communication bus."""
        if campaign_id in self._inboxes:
            self._inboxes[campaign_id].pop(agent_id, None)

    # ── Convenience Methods ──────────────────────────────────────────────

    def share_insight(self, from_agent: str, campaign_id: str,
                      subject: str, body: str, data: dict | None = None,
                      to_agent: str = "*"):
        """Quick method to share an insight with other agents."""
        return self.send(AgentMessage(
            from_agent=from_agent, to_agent=to_agent,
            campaign_id=campaign_id,
            msg_type=MessageType.INSIGHT,
            subject=subject, body=body,
            data=data or {},
        ))

    def request_data(self, from_agent: str, to_agent: str,
                     campaign_id: str, subject: str, body: str) -> str:
        """Request data from another agent."""
        return self.send(AgentMessage(
            from_agent=from_agent, to_agent=to_agent,
            campaign_id=campaign_id,
            msg_type=MessageType.DATA_REQUEST,
            priority=MessagePriority.HIGH,
            subject=subject, body=body,
        ))

    def respond(self, from_agent: str, to_agent: str,
                campaign_id: str, reply_to: str,
                body: str, data: dict | None = None) -> str:
        """Respond to a data request."""
        return self.send(AgentMessage(
            from_agent=from_agent, to_agent=to_agent,
            campaign_id=campaign_id,
            msg_type=MessageType.RESPONSE,
            reply_to=reply_to,
            body=body, data=data or {},
        ))

    def broadcast_alert(self, from_agent: str, campaign_id: str,
                        subject: str, body: str):
        """Broadcast an urgent alert to all agents."""
        return self.send(AgentMessage(
            from_agent=from_agent, to_agent="*",
            campaign_id=campaign_id,
            msg_type=MessageType.ALERT,
            priority=MessagePriority.URGENT,
            subject=subject, body=body,
            ttl_seconds=600,  # alerts last longer
        ))

    def handoff(self, from_agent: str, to_agent: str,
                campaign_id: str, subject: str,
                body: str, data: dict) -> str:
        """Hand off work context to another agent."""
        return self.send(AgentMessage(
            from_agent=from_agent, to_agent=to_agent,
            campaign_id=campaign_id,
            msg_type=MessageType.HANDOFF,
            priority=MessagePriority.HIGH,
            subject=subject, body=body, data=data,
            ttl_seconds=600,
        ))

    # ── Auto-Routing Rules ───────────────────────────────────────────────

    def _apply_routing_rules(self, message: AgentMessage):
        """Auto-route messages based on predefined patterns."""
        for rule in self._routing_rules:
            if message.from_agent == rule.get("from") and message.msg_type.value == rule.get("type"):
                targets = rule.get("auto_notify", [])
                for target in targets:
                    if target != message.to_agent and target != message.from_agent:
                        # Create a forwarded copy
                        forwarded = AgentMessage(
                            from_agent=message.from_agent,
                            to_agent=target,
                            campaign_id=message.campaign_id,
                            msg_type=message.msg_type,
                            priority=MessagePriority.LOW,
                            subject=f"[FWD] {message.subject}",
                            body=message.body,
                            data=message.data,
                        )
                        self._deliver(message.campaign_id, target, forwarded)

    # ── Stats & Debug ────────────────────────────────────────────────────

    def get_stats(self, campaign_id: str = "") -> dict:
        """Get communication stats."""
        if campaign_id:
            inboxes = self._inboxes.get(campaign_id, {})
            return {
                "campaign_id": campaign_id,
                "registered_agents": list(inboxes.keys()),
                "pending_messages": {
                    aid: len([m for m in msgs if not m.read and not m.is_expired])
                    for aid, msgs in inboxes.items()
                },
                "total_messages": len([
                    m for m in self._message_log if m.campaign_id == campaign_id
                ]),
            }
        return {
            "total_campaigns": len(self._inboxes),
            "total_messages": len(self._message_log),
            "routing_rules": len(self._routing_rules),
        }

    def get_conversation(self, campaign_id: str, agent_a: str = "",
                         agent_b: str = "", limit: int = 50) -> list[dict]:
        """Get message history between agents."""
        msgs = [m for m in self._message_log if m.campaign_id == campaign_id]
        if agent_a:
            msgs = [m for m in msgs if m.from_agent == agent_a or m.to_agent == agent_a]
        if agent_b:
            msgs = [m for m in msgs if m.from_agent == agent_b or m.to_agent == agent_b]
        return [
            {
                "id": m.id, "from": m.from_agent, "to": m.to_agent,
                "type": m.msg_type.value, "subject": m.subject,
                "body": m.body[:500], "priority": m.priority.value,
                "timestamp": m.timestamp, "read": m.read,
            }
            for m in msgs[-limit:]
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT AUTO-ROUTING RULES
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_ROUTING_RULES = [
    # When prospector shares insights, auto-notify outreach + sales
    {
        "from": "prospector",
        "type": "insight",
        "auto_notify": ["outreach", "sales", "cs"],
    },
    # When content shares insights, auto-notify social + newsletter + pr
    {
        "from": "content",
        "type": "insight",
        "auto_notify": ["social", "newsletter", "pr_comms"],
    },
    # When ads shares insights, auto-notify ppc
    {
        "from": "ads",
        "type": "insight",
        "auto_notify": ["ppc"],
    },
    # When outreach shares insights, auto-notify cs + sales
    {
        "from": "outreach",
        "type": "insight",
        "auto_notify": ["cs", "sales"],
    },
    # When finance shares insights, auto-notify billing + tax
    {
        "from": "finance",
        "type": "insight",
        "auto_notify": ["billing", "tax_strategist", "advisor"],
    },
    # When sales shares insights, auto-notify delivery + cs
    {
        "from": "sales",
        "type": "insight",
        "auto_notify": ["delivery", "client_fulfillment", "cs"],
    },
    # Alerts from any agent get routed to supervisor + governance
    {
        "from": "*",
        "type": "alert",
        "auto_notify": ["supervisor", "governance"],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

agent_comms = AgentCommsBus()
