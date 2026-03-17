"""
Supervisor Backend — Revenue Share Pricing Engine
Outcome-based pricing: users pay a % of revenue attributed to agent actions.
Competes with Polsia's 20% rev-share model.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.revshare")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class RevShareTier(BaseModel):
    """Revenue share plan configuration."""
    name: str
    base_monthly: float = 0.0          # $0 base for pure rev-share
    rev_share_pct: float = 15.0        # % of attributed revenue
    min_monthly: float = 0.0           # Minimum monthly charge
    max_monthly_cap: float = 0.0       # Cap (0 = unlimited)
    attribution_window_days: int = 30  # How long after agent action to attribute revenue
    reconciliation_period: str = "monthly"  # monthly | weekly
    agents: str = "__all__"            # Agent access
    llm_tier_cap: str = "strong"


class RevenueAttribution(BaseModel):
    """Maps a revenue event back to the agent action that caused it."""
    id: str = Field(default_factory=lambda: f"attr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    campaign_id: str
    revenue_event_id: str
    agent_id: str
    agent_run_id: str = ""
    action_type: str = ""              # email_sent, ad_click, call_booked, etc.
    revenue_amount: float = 0.0
    currency: str = "USD"
    attribution_confidence: float = 1.0  # 0.0-1.0 (multi-touch lowers this)
    attributed_at: datetime = Field(default_factory=datetime.utcnow)
    action_timestamp: datetime | None = None


class RevShareInvoice(BaseModel):
    """Monthly reconciliation invoice for rev-share customers."""
    id: str = Field(default_factory=lambda: f"inv_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    user_id: str
    campaign_id: str
    period_start: datetime
    period_end: datetime
    gross_revenue: float = 0.0         # Total revenue in period
    attributed_revenue: float = 0.0    # Revenue attributed to agents
    rev_share_pct: float = 15.0
    rev_share_amount: float = 0.0      # What they owe us
    base_fee: float = 0.0
    total_due: float = 0.0
    status: str = "draft"              # draft | sent | paid | overdue
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attributions: list[RevenueAttribution] = []


# ═══════════════════════════════════════════════════════════════════════════════
# PLANS
# ═══════════════════════════════════════════════════════════════════════════════

REVSHARE_PLANS = {
    "growth": RevShareTier(
        name="Growth",
        base_monthly=0,
        rev_share_pct=15.0,
        min_monthly=29,
        max_monthly_cap=2000,
        attribution_window_days=30,
        llm_tier_cap="standard",
    ),
    "scale": RevShareTier(
        name="Scale",
        base_monthly=0,
        rev_share_pct=10.0,
        min_monthly=99,
        max_monthly_cap=10000,
        attribution_window_days=45,
        llm_tier_cap="strong",
    ),
    "partner": RevShareTier(
        name="Partner",
        base_monthly=0,
        rev_share_pct=7.5,
        min_monthly=249,
        max_monthly_cap=0,  # No cap
        attribution_window_days=60,
        llm_tier_cap="strong",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# ATTRIBUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class AttributionEngine:
    """
    Multi-touch attribution: maps revenue events to agent actions.
    Supports last-touch, first-touch, and linear attribution models.
    """

    ATTRIBUTION_MODELS = ["last_touch", "first_touch", "linear", "time_decay"]

    def __init__(self):
        self._attributions: dict[str, list[RevenueAttribution]] = {}  # campaign_id -> attributions
        self._agent_actions: dict[str, list[dict]] = {}  # campaign_id -> action log
        self._model = "last_touch"

    def set_model(self, model: str):
        if model in self.ATTRIBUTION_MODELS:
            self._model = model

    def log_agent_action(self, campaign_id: str, agent_id: str, action_type: str,
                         run_id: str = "", metadata: dict = None):
        """Record an agent action that could later be attributed to revenue."""
        if campaign_id not in self._agent_actions:
            self._agent_actions[campaign_id] = []
        self._agent_actions[campaign_id].append({
            "agent_id": agent_id,
            "action_type": action_type,
            "run_id": run_id,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {},
        })
        logger.debug(f"Logged action: {agent_id}/{action_type} for campaign {campaign_id}")

    def attribute_revenue(self, campaign_id: str, revenue_event_id: str,
                          amount: float, currency: str = "USD",
                          window_days: int = 30) -> list[RevenueAttribution]:
        """
        Attribute a revenue event to agent action(s) within the attribution window.
        Returns list of attributions (multiple for linear/time-decay models).
        """
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        actions = [
            a for a in self._agent_actions.get(campaign_id, [])
            if a["timestamp"] >= cutoff
        ]

        if not actions:
            return []

        attributions = []
        if self._model == "last_touch":
            action = actions[-1]
            attr = RevenueAttribution(
                campaign_id=campaign_id, revenue_event_id=revenue_event_id,
                agent_id=action["agent_id"], agent_run_id=action["run_id"],
                action_type=action["action_type"], revenue_amount=amount,
                currency=currency, attribution_confidence=1.0,
                action_timestamp=action["timestamp"],
            )
            attributions.append(attr)

        elif self._model == "first_touch":
            action = actions[0]
            attr = RevenueAttribution(
                campaign_id=campaign_id, revenue_event_id=revenue_event_id,
                agent_id=action["agent_id"], agent_run_id=action["run_id"],
                action_type=action["action_type"], revenue_amount=amount,
                currency=currency, attribution_confidence=1.0,
                action_timestamp=action["timestamp"],
            )
            attributions.append(attr)

        elif self._model == "linear":
            share = amount / len(actions) if actions else 0
            confidence = 1.0 / len(actions) if actions else 0
            for action in actions:
                attr = RevenueAttribution(
                    campaign_id=campaign_id, revenue_event_id=revenue_event_id,
                    agent_id=action["agent_id"], agent_run_id=action["run_id"],
                    action_type=action["action_type"], revenue_amount=share,
                    currency=currency, attribution_confidence=confidence,
                    action_timestamp=action["timestamp"],
                )
                attributions.append(attr)

        elif self._model == "time_decay":
            # More recent actions get higher attribution
            now = datetime.utcnow()
            weights = []
            for action in actions:
                age_hours = max((now - action["timestamp"]).total_seconds() / 3600, 1)
                weights.append(1.0 / age_hours)
            total_weight = sum(weights) or 1
            for action, weight in zip(actions, weights):
                share = amount * (weight / total_weight)
                attr = RevenueAttribution(
                    campaign_id=campaign_id, revenue_event_id=revenue_event_id,
                    agent_id=action["agent_id"], agent_run_id=action["run_id"],
                    action_type=action["action_type"], revenue_amount=share,
                    currency=currency, attribution_confidence=weight / total_weight,
                    action_timestamp=action["timestamp"],
                )
                attributions.append(attr)

        # Store attributions
        if campaign_id not in self._attributions:
            self._attributions[campaign_id] = []
        self._attributions[campaign_id].extend(attributions)

        logger.info(f"Attributed ${amount:.2f} to {len(attributions)} action(s) for campaign {campaign_id}")
        return attributions

    def get_attributions(self, campaign_id: str,
                         since: datetime = None) -> list[RevenueAttribution]:
        """Get all attributions for a campaign, optionally filtered by date."""
        attrs = self._attributions.get(campaign_id, [])
        if since:
            attrs = [a for a in attrs if a.attributed_at >= since]
        return attrs

    def get_agent_revenue(self, campaign_id: str, agent_id: str = None) -> dict:
        """Get revenue breakdown by agent for a campaign."""
        attrs = self._attributions.get(campaign_id, [])
        by_agent: dict[str, float] = {}
        for a in attrs:
            if agent_id and a.agent_id != agent_id:
                continue
            by_agent[a.agent_id] = by_agent.get(a.agent_id, 0) + a.revenue_amount
        return by_agent


# ═══════════════════════════════════════════════════════════════════════════════
# INVOICE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class RevShareBilling:
    """Generates monthly invoices based on attributed revenue."""

    def __init__(self, attribution_engine: AttributionEngine):
        self.attr = attribution_engine
        self._invoices: dict[str, RevShareInvoice] = {}  # invoice_id -> invoice
        self._user_plans: dict[str, str] = {}  # user_id -> plan_name

    def set_user_plan(self, user_id: str, plan_name: str):
        if plan_name not in REVSHARE_PLANS:
            raise ValueError(f"Unknown rev-share plan: {plan_name}")
        self._user_plans[user_id] = plan_name
        logger.info(f"User {user_id} enrolled in rev-share plan: {plan_name}")

    def get_user_plan(self, user_id: str) -> Optional[RevShareTier]:
        plan_name = self._user_plans.get(user_id)
        return REVSHARE_PLANS.get(plan_name) if plan_name else None

    def generate_invoice(self, user_id: str, campaign_id: str,
                         period_start: datetime = None,
                         period_end: datetime = None) -> RevShareInvoice:
        """Generate a rev-share invoice for a billing period."""
        plan = self.get_user_plan(user_id)
        if not plan:
            raise ValueError(f"User {user_id} not enrolled in a rev-share plan")

        period_end = period_end or datetime.utcnow()
        period_start = period_start or (period_end - timedelta(days=30))

        # Get all attributions in period
        attributions = self.attr.get_attributions(campaign_id, since=period_start)
        attributions = [a for a in attributions if a.attributed_at <= period_end]

        attributed_revenue = sum(a.revenue_amount for a in attributions)
        rev_share_amount = attributed_revenue * (plan.rev_share_pct / 100)

        # Apply min/max
        total_due = max(rev_share_amount + plan.base_monthly, plan.min_monthly)
        if plan.max_monthly_cap > 0:
            total_due = min(total_due, plan.max_monthly_cap)

        invoice = RevShareInvoice(
            user_id=user_id, campaign_id=campaign_id,
            period_start=period_start, period_end=period_end,
            attributed_revenue=attributed_revenue,
            rev_share_pct=plan.rev_share_pct,
            rev_share_amount=rev_share_amount,
            base_fee=plan.base_monthly,
            total_due=total_due,
            attributions=attributions,
        )

        self._invoices[invoice.id] = invoice
        logger.info(f"Generated invoice {invoice.id}: ${total_due:.2f} ({plan.rev_share_pct}% of ${attributed_revenue:.2f})")
        return invoice

    def get_invoices(self, user_id: str = None) -> list[RevShareInvoice]:
        invoices = list(self._invoices.values())
        if user_id:
            invoices = [i for i in invoices if i.user_id == user_id]
        return sorted(invoices, key=lambda i: i.created_at, reverse=True)

    def mark_paid(self, invoice_id: str) -> bool:
        inv = self._invoices.get(invoice_id)
        if inv:
            inv.status = "paid"
            return True
        return False

    def get_revenue_dashboard(self, user_id: str) -> dict:
        """Get revenue dashboard for a rev-share user."""
        plan = self.get_user_plan(user_id)
        invoices = self.get_invoices(user_id)
        total_paid = sum(i.total_due for i in invoices if i.status == "paid")
        total_attributed = sum(i.attributed_revenue for i in invoices)
        return {
            "plan": plan.model_dump() if plan else None,
            "total_invoices": len(invoices),
            "total_paid": total_paid,
            "total_attributed_revenue": total_attributed,
            "effective_rate": (total_paid / total_attributed * 100) if total_attributed > 0 else 0,
            "invoices": [i.model_dump() for i in invoices[:10]],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════════

attribution_engine = AttributionEngine()
revshare_billing = RevShareBilling(attribution_engine)
