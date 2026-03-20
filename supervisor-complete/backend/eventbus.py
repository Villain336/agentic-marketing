"""
Omni OS Backend — Event Bus & Cross-Agent Pipeline Triggers

Event-driven pub/sub system enabling agents to trigger other agents
based on outputs, thresholds, and state changes. Replaces purely
sequential orchestration with reactive pipelines.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger("supervisor.eventbus")


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class EventType(str, Enum):
    # Agent lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # Tool execution
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # Data thresholds
    PROSPECTS_FOUND = "data.prospects_found"
    CONTENT_READY = "data.content_ready"
    SITE_DEPLOYED = "data.site_deployed"
    EMAILS_SENT = "data.emails_sent"
    REVENUE_RECEIVED = "data.revenue_received"
    DEAL_STAGE_CHANGED = "data.deal_stage_changed"
    LEAD_SCORED = "data.lead_scored"

    # Approval flow
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"

    # System
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_RESUMED = "campaign.resumed"
    HEALTH_CHECK_FAILED = "health.check_failed"
    BUDGET_THRESHOLD = "budget.threshold_reached"

    # Custom / user-defined
    CUSTOM = "custom"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: EventType
    source_agent: str = ""
    campaign_id: str = ""
    data: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TriggerRule(BaseModel):
    """A rule that maps an event to an action (run agent, send notification, etc.)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    event_type: EventType
    source_agent: str = ""           # filter: only fire if from this agent ("" = any)
    condition: dict[str, Any] = {}   # optional: key-value conditions on event.data
    action: str = ""                 # "run_agent", "notify", "pause_agent", "escalate"
    target_agent: str = ""           # which agent to trigger
    target_data: dict[str, Any] = {} # extra data passed to the action
    enabled: bool = True
    cooldown_seconds: int = 60       # min time between firings
    last_fired: float = 0            # epoch timestamp

    def matches(self, event: Event) -> bool:
        if not self.enabled:
            return False
        if event.type != self.event_type:
            return False
        if self.source_agent and event.source_agent != self.source_agent:
            return False
        # Check conditions on event data
        for key, expected in self.condition.items():
            actual = event.data.get(key)
            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                val = expected.get("value")
                if op == "gte" and (actual is None or actual < val):
                    return False
                elif op == "lte" and (actual is None or actual > val):
                    return False
                elif op == "eq" and actual != val:
                    return False
                elif op == "contains" and (actual is None or val not in str(actual)):
                    return False
            elif actual != expected:
                return False
        # Cooldown check
        if self.cooldown_seconds and (time.time() - self.last_fired) < self.cooldown_seconds:
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT TRIGGER RULES — Cross-Agent Pipelines
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_TRIGGERS: list[dict] = [
    # Prospector → Outreach: when prospects found, trigger outreach
    {
        "name": "prospects_trigger_outreach",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "prospector",
        "condition": {},
        "action": "run_agent",
        "target_agent": "outreach",
    },
    # Prospector → Sales: when prospects found, trigger sales ops
    {
        "name": "prospects_trigger_sales",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "prospector",
        "condition": {},
        "action": "run_agent",
        "target_agent": "sales",
    },
    # Content → Social: content ready triggers social scheduling
    {
        "name": "content_triggers_social",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "content",
        "condition": {},
        "action": "run_agent",
        "target_agent": "social",
    },
    # Content → Newsletter: content triggers newsletter
    {
        "name": "content_triggers_newsletter",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "content",
        "condition": {},
        "action": "run_agent",
        "target_agent": "newsletter",
    },
    # Content → Site Launch: content triggers site build
    {
        "name": "content_triggers_sitelaunch",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "content",
        "condition": {},
        "action": "run_agent",
        "target_agent": "sitelaunch",
    },
    # Outreach + Content → CS: both done triggers client success
    {
        "name": "outreach_triggers_cs",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "outreach",
        "condition": {},
        "action": "run_agent",
        "target_agent": "cs",
    },
    # Ads → PPC: ad creation triggers PPC optimization
    {
        "name": "ads_triggers_ppc",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "ads",
        "condition": {},
        "action": "run_agent",
        "target_agent": "ppc",
    },
    # Finance → Tax: financial plan triggers tax strategy
    {
        "name": "finance_triggers_tax",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "finance",
        "condition": {},
        "action": "run_agent",
        "target_agent": "tax_strategist",
    },
    # Finance + Tax → Wealth: both trigger wealth architecture
    {
        "name": "tax_triggers_wealth",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "tax_strategist",
        "condition": {},
        "action": "run_agent",
        "target_agent": "wealth_architect",
    },
    # Finance → Billing: financial plan triggers billing setup
    {
        "name": "finance_triggers_billing",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "finance",
        "condition": {},
        "action": "run_agent",
        "target_agent": "billing",
    },
    # Outreach + CS → Referral: pipeline ready triggers referral program
    {
        "name": "cs_triggers_referral",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "cs",
        "condition": {},
        "action": "run_agent",
        "target_agent": "referral",
    },
    # Site Launch → Fullstack Dev: site spec triggers dev
    {
        "name": "site_triggers_fullstack",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "sitelaunch",
        "condition": {},
        "action": "run_agent",
        "target_agent": "fullstack_dev",
    },
    # Sales → Delivery: pipeline triggers delivery system
    {
        "name": "sales_triggers_delivery",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "sales",
        "condition": {},
        "action": "run_agent",
        "target_agent": "delivery",
    },
    # Delivery → Client Fulfillment
    {
        "name": "delivery_triggers_fulfillment",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "delivery",
        "condition": {},
        "action": "run_agent",
        "target_agent": "client_fulfillment",
    },
    # Analytics → Data Engineer: analytics triggers data layer
    {
        "name": "analytics_triggers_data_eng",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "analytics_agent",
        "condition": {},
        "action": "run_agent",
        "target_agent": "data_engineer",
    },
    # Content → PR: content ready triggers PR/comms
    {
        "name": "content_triggers_pr",
        "event_type": EventType.AGENT_COMPLETED,
        "source_agent": "content",
        "condition": {},
        "action": "run_agent",
        "target_agent": "pr_comms",
    },
    # Revenue event → notify owner
    {
        "name": "revenue_notify",
        "event_type": EventType.REVENUE_RECEIVED,
        "source_agent": "",
        "condition": {},
        "action": "notify",
        "target_agent": "",
        "target_data": {"channel": "owner", "template": "revenue_received"},
    },
    # Budget threshold → pause and escalate
    {
        "name": "budget_escalate",
        "event_type": EventType.BUDGET_THRESHOLD,
        "source_agent": "",
        "condition": {},
        "action": "notify",
        "target_agent": "",
        "target_data": {"channel": "owner", "template": "budget_alert"},
    },
    # Health check failure → escalate
    {
        "name": "health_failure_escalate",
        "event_type": EventType.HEALTH_CHECK_FAILED,
        "source_agent": "",
        "condition": {},
        "action": "notify",
        "target_agent": "",
        "target_data": {"channel": "owner", "template": "health_alert"},
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT BUS — Pub/Sub + Trigger Execution
# ═══════════════════════════════════════════════════════════════════════════════

# Type for async event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Central event bus for cross-agent communication.
    Supports:
    - Pub/sub: arbitrary handlers subscribe to event types
    - Trigger rules: declarative rules that fire actions on events
    - Event log: recent events for debugging/display
    """

    def __init__(self):
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._triggers: dict[str, TriggerRule] = {}
        self._event_log: list[Event] = []
        self._max_log_size = 500
        self._action_handlers: dict[str, EventHandler] = {}
        self._pending_agents: dict[str, set[str]] = {}  # campaign_id -> set of triggered agent IDs

        # Load default triggers
        for t in DEFAULT_TRIGGERS:
            rule = TriggerRule(**t)
            self._triggers[rule.id] = rule

    # ── Subscription API ──────────────────────────────────────────────────

    def subscribe(self, event_type: EventType, handler: EventHandler):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    # ── Trigger Rule Management ───────────────────────────────────────────

    def add_trigger(self, rule: TriggerRule) -> str:
        self._triggers[rule.id] = rule
        logger.info(f"Trigger added: {rule.name} ({rule.id})")
        return rule.id

    def remove_trigger(self, rule_id: str):
        self._triggers.pop(rule_id, None)

    def update_trigger(self, rule_id: str, updates: dict):
        rule = self._triggers.get(rule_id)
        if rule:
            for k, v in updates.items():
                if hasattr(rule, k):
                    setattr(rule, k, v)

    def get_triggers(self) -> list[TriggerRule]:
        return list(self._triggers.values())

    def get_trigger(self, rule_id: str) -> TriggerRule | None:
        return self._triggers.get(rule_id)

    # ── Action Handler Registration ───────────────────────────────────────

    def register_action(self, action_name: str, handler: EventHandler):
        """Register a handler for a trigger action type (e.g., 'run_agent', 'notify')."""
        self._action_handlers[action_name] = handler

    # ── Event Publishing ──────────────────────────────────────────────────

    async def emit(self, event: Event):
        """Publish an event. Fires subscribers and matching trigger rules."""
        # Log event in memory
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        # Persist to database
        try:
            import db
            asyncio.create_task(db.save_event(event.model_dump()))
        except Exception:
            pass

        logger.info(
            f"Event: {event.type.value} from={event.source_agent} "
            f"campaign={event.campaign_id} data_keys={list(event.data.keys())}"
        )

        # Fire subscribers
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.type}: {e}")

        # Fire matching triggers
        for rule in list(self._triggers.values()):
            if rule.matches(event):
                rule.last_fired = time.time()
                logger.info(
                    f"Trigger fired: {rule.name} → {rule.action}({rule.target_agent})"
                )
                action_handler = self._action_handlers.get(rule.action)
                if action_handler:
                    try:
                        # Pass rule info in the event data for the action handler
                        action_event = Event(
                            type=event.type,
                            source_agent=event.source_agent,
                            campaign_id=event.campaign_id,
                            data={
                                **event.data,
                                "_trigger_rule": rule.id,
                                "_trigger_name": rule.name,
                                "_target_agent": rule.target_agent,
                                "_target_data": rule.target_data,
                                "_action": rule.action,
                            },
                        )
                        asyncio.create_task(action_handler(action_event))
                    except Exception as e:
                        logger.error(f"Action handler error for {rule.name}: {e}")
                else:
                    logger.warning(f"No handler for action '{rule.action}'")

    # ── Convenience Emitters ──────────────────────────────────────────────

    async def agent_started(self, agent_id: str, campaign_id: str):
        await self.emit(Event(
            type=EventType.AGENT_STARTED,
            source_agent=agent_id,
            campaign_id=campaign_id,
        ))

    async def agent_completed(self, agent_id: str, campaign_id: str,
                              memory_update: dict | None = None):
        await self.emit(Event(
            type=EventType.AGENT_COMPLETED,
            source_agent=agent_id,
            campaign_id=campaign_id,
            data={"memory_update": memory_update or {}},
        ))

    async def agent_failed(self, agent_id: str, campaign_id: str, error: str = ""):
        await self.emit(Event(
            type=EventType.AGENT_FAILED,
            source_agent=agent_id,
            campaign_id=campaign_id,
            data={"error": error},
        ))

    async def tool_executed(self, tool_name: str, agent_id: str,
                            campaign_id: str, success: bool, output: str = ""):
        await self.emit(Event(
            type=EventType.TOOL_EXECUTED if success else EventType.TOOL_FAILED,
            source_agent=agent_id,
            campaign_id=campaign_id,
            data={"tool": tool_name, "success": success, "output_preview": output[:200]},
        ))

    async def approval_requested(self, agent_id: str, campaign_id: str,
                                  action_type: str, content: dict):
        await self.emit(Event(
            type=EventType.APPROVAL_REQUESTED,
            source_agent=agent_id,
            campaign_id=campaign_id,
            data={"action_type": action_type, "content": content},
        ))

    async def approval_decided(self, agent_id: str, campaign_id: str,
                                approved: bool, item_id: str = ""):
        await self.emit(Event(
            type=EventType.APPROVAL_DECIDED,
            source_agent=agent_id,
            campaign_id=campaign_id,
            data={"approved": approved, "item_id": item_id},
        ))

    # ── Event Log ─────────────────────────────────────────────────────────

    def get_recent_events(self, limit: int = 50, campaign_id: str = "",
                          event_type: str = "") -> list[dict]:
        events = self._event_log
        if campaign_id:
            events = [e for e in events if e.campaign_id == campaign_id]
        if event_type:
            events = [e for e in events if e.type.value == event_type]
        results = [e.model_dump() for e in events[-limit:]]
        # If no in-memory events, try loading from DB (post-restart)
        if not results:
            try:
                import db
                if db.is_persistent():
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Can't await in sync context; return empty and let API endpoint handle it
                        pass
            except Exception:
                pass
        return results

    def get_pending_agents(self, campaign_id: str) -> set[str]:
        """Get agents that have been triggered but not yet started for a campaign."""
        return self._pending_agents.get(campaign_id, set())

    def mark_agent_started(self, campaign_id: str, agent_id: str):
        if campaign_id in self._pending_agents:
            self._pending_agents[campaign_id].discard(agent_id)

    def mark_agent_pending(self, campaign_id: str, agent_id: str):
        if campaign_id not in self._pending_agents:
            self._pending_agents[campaign_id] = set()
        self._pending_agents[campaign_id].add(agent_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

event_bus = EventBus()
