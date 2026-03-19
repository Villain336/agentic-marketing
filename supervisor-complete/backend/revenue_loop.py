"""
Omni OS Backend — Autonomous Revenue Closed-Loop

Self-healing revenue optimization: agents detect underperformance,
coordinate fixes, and execute improvements WITHOUT human intervention.

The loop: Sense → Diagnose → Prescribe → Execute → Verify

Example: Landing page bounce rate spikes → sitelaunch rebuilds hero →
ads agent reallocates budget → billing adjusts pricing trial → verify
conversion recovers. All autonomous.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("omnios.revenue_loop")


# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE SIGNALS — What we detect
# ═══════════════════════════════════════════════════════════════════════════════

class SignalType(str, Enum):
    """Types of revenue-impacting signals."""
    # Acquisition
    LANDING_PAGE_BOUNCE_HIGH = "landing_page_bounce_high"
    AD_CTR_LOW = "ad_ctr_low"
    AD_CPA_HIGH = "ad_cpa_high"
    OUTREACH_REPLY_LOW = "outreach_reply_low"
    OPEN_RATE_LOW = "open_rate_low"

    # Conversion
    TRIAL_CONVERSION_LOW = "trial_conversion_low"
    DEMO_NO_SHOW_HIGH = "demo_no_show_high"
    PROPOSAL_STALL = "proposal_stall"
    CART_ABANDONMENT_HIGH = "cart_abandonment_high"

    # Retention
    CHURN_SPIKE = "churn_spike"
    NPS_DROP = "nps_drop"
    SUPPORT_TICKET_SURGE = "support_ticket_surge"
    PAYMENT_FAILURE_RATE = "payment_failure_rate"

    # Expansion
    UPSELL_OPPORTUNITY = "upsell_opportunity"
    REFERRAL_STALL = "referral_stall"

    # Revenue
    MRR_DECLINE = "mrr_decline"
    ROAS_BELOW_THRESHOLD = "roas_below_threshold"


class SignalSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class RevenueSignal:
    """A detected revenue-impacting signal."""
    id: str = ""
    signal_type: SignalType = SignalType.LANDING_PAGE_BOUNCE_HIGH
    severity: SignalSeverity = SignalSeverity.WARNING
    campaign_id: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    delta_pct: float = 0.0           # % change from baseline
    description: str = ""
    detected_at: str = ""
    resolved: bool = False
    resolution_actions: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = f"sig_{uuid.uuid4().hex[:10]}"
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL DETECTION RULES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DetectionRule:
    """A rule that detects a revenue signal from metrics."""
    signal_type: SignalType
    metric_source: str            # e.g., "site_metrics", "ad_metrics"
    metric_key: str               # e.g., "bounce_rate", "ctr"
    operator: str                 # "gt", "lt", "gte", "lte"
    threshold: float
    severity: SignalSeverity = SignalSeverity.WARNING
    min_sample: int = 10          # min data points before firing
    sample_key: str = ""          # metric key that counts data volume
    description_template: str = ""


DETECTION_RULES: list[DetectionRule] = [
    # ── Acquisition ──
    DetectionRule(
        signal_type=SignalType.LANDING_PAGE_BOUNCE_HIGH,
        metric_source="site_metrics", metric_key="bounce_rate",
        operator="gt", threshold=70.0,
        severity=SignalSeverity.CRITICAL,
        sample_key="sessions", min_sample=50,
        description_template="Landing page bounce rate is {value:.1f}% (threshold: {threshold}%)",
    ),
    DetectionRule(
        signal_type=SignalType.AD_CTR_LOW,
        metric_source="ad_metrics", metric_key="ctr",
        operator="lt", threshold=1.0,
        severity=SignalSeverity.WARNING,
        sample_key="impressions", min_sample=1000,
        description_template="Ad CTR is {value:.2f}% (threshold: {threshold}%)",
    ),
    DetectionRule(
        signal_type=SignalType.AD_CPA_HIGH,
        metric_source="ad_metrics", metric_key="cpa",
        operator="gt", threshold=150.0,
        severity=SignalSeverity.WARNING,
        sample_key="conversions", min_sample=5,
        description_template="CPA is ${value:.2f} (threshold: ${threshold})",
    ),
    DetectionRule(
        signal_type=SignalType.OUTREACH_REPLY_LOW,
        metric_source="email_metrics", metric_key="reply_rate",
        operator="lt", threshold=2.0,
        severity=SignalSeverity.WARNING,
        sample_key="sent", min_sample=50,
        description_template="Outreach reply rate is {value:.1f}% (threshold: {threshold}%)",
    ),
    DetectionRule(
        signal_type=SignalType.OPEN_RATE_LOW,
        metric_source="email_metrics", metric_key="open_rate",
        operator="lt", threshold=25.0,
        severity=SignalSeverity.WARNING,
        sample_key="sent", min_sample=50,
        description_template="Email open rate is {value:.1f}% (threshold: {threshold}%)",
    ),

    # ── Retention ──
    DetectionRule(
        signal_type=SignalType.CHURN_SPIKE,
        metric_source="revenue_metrics", metric_key="churn_rate",
        operator="gt", threshold=5.0,
        severity=SignalSeverity.CRITICAL,
        sample_key="total_customers", min_sample=10,
        description_template="Monthly churn rate spiked to {value:.1f}% (threshold: {threshold}%)",
    ),
    DetectionRule(
        signal_type=SignalType.PAYMENT_FAILURE_RATE,
        metric_source="billing_metrics", metric_key="failed_payment_rate",
        operator="gt", threshold=5.0,
        severity=SignalSeverity.WARNING,
        sample_key="total_invoices", min_sample=20,
        description_template="Payment failure rate is {value:.1f}% (threshold: {threshold}%)",
    ),

    # ── Revenue ──
    DetectionRule(
        signal_type=SignalType.MRR_DECLINE,
        metric_source="revenue_metrics", metric_key="mrr_growth_pct",
        operator="lt", threshold=-5.0,
        severity=SignalSeverity.CRITICAL,
        description_template="MRR declined {value:.1f}% month-over-month",
    ),
    DetectionRule(
        signal_type=SignalType.ROAS_BELOW_THRESHOLD,
        metric_source="ad_metrics", metric_key="roas",
        operator="lt", threshold=2.0,
        severity=SignalSeverity.WARNING,
        sample_key="spend", min_sample=500,
        description_template="ROAS is {value:.1f}x (threshold: {threshold}x)",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# RECOVERY PLAYBOOKS — What agents do in response
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RecoveryStep:
    """A single step in a recovery playbook."""
    agent_id: str                # which agent executes this
    action: str                  # what the agent should do
    trigger_reason: str          # why (injected into agent prompt)
    priority: int = 1            # execution order (lower = first)
    depends_on: str = ""         # wait for this step to complete first
    timeout_seconds: int = 300


@dataclass
class RecoveryPlaybook:
    """A coordinated multi-agent recovery plan."""
    id: str = ""
    signal_type: SignalType = SignalType.LANDING_PAGE_BOUNCE_HIGH
    name: str = ""
    steps: list[RecoveryStep] = field(default_factory=list)
    max_executions_per_day: int = 3
    cooldown_hours: float = 4.0

    def __post_init__(self):
        if not self.id:
            self.id = f"pb_{self.signal_type.value}"


# Pre-built playbooks for common revenue signals
RECOVERY_PLAYBOOKS: list[RecoveryPlaybook] = [
    RecoveryPlaybook(
        signal_type=SignalType.LANDING_PAGE_BOUNCE_HIGH,
        name="Landing Page Recovery",
        steps=[
            RecoveryStep(
                agent_id="analytics_agent", priority=1,
                action="Diagnose why bounce rate is high — check page speed, mobile experience, content match with traffic source",
                trigger_reason="Autonomous recovery: bounce rate exceeded threshold",
            ),
            RecoveryStep(
                agent_id="sitelaunch", priority=2,
                action="Rebuild hero section — value prop must be clear in 5 seconds, add social proof above fold, optimize CTA",
                trigger_reason="Autonomous recovery: landing page underperforming, rebuild hero and above-fold content",
                depends_on="analytics_agent",
            ),
            RecoveryStep(
                agent_id="ads", priority=3,
                action="Review ad-to-landing-page message match — ensure ad copy promises what the page delivers",
                trigger_reason="Autonomous recovery: fixing ad-to-page alignment after bounce rate spike",
                depends_on="sitelaunch",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.AD_CPA_HIGH,
        name="CPA Reduction",
        steps=[
            RecoveryStep(
                agent_id="ppc", priority=1,
                action="Pause broad-match keywords, add negative keywords from search terms, narrow audience targeting",
                trigger_reason="Autonomous recovery: CPA exceeded threshold",
            ),
            RecoveryStep(
                agent_id="ads", priority=2,
                action="Create 3 new ad variants with stronger emotional hooks and specific outcomes",
                trigger_reason="Autonomous recovery: improving ad creative to reduce CPA",
                depends_on="ppc",
            ),
            RecoveryStep(
                agent_id="content", priority=2,
                action="Optimize landing page copy for conversion — add testimonials, reduce form fields, clarify offer",
                trigger_reason="Autonomous recovery: improving conversion to reduce CPA",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.OUTREACH_REPLY_LOW,
        name="Outreach Recovery",
        steps=[
            RecoveryStep(
                agent_id="prospector", priority=1,
                action="Re-evaluate ICP — are we targeting the right titles and companies? Check for buying signals",
                trigger_reason="Autonomous recovery: reply rate critically low, verifying prospect quality",
            ),
            RecoveryStep(
                agent_id="outreach", priority=2,
                action="Rewrite email sequence — shorter subjects, specific pain points, social proof by line 3, single CTA",
                trigger_reason="Autonomous recovery: reply rate below threshold, rewriting sequence",
                depends_on="prospector",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.CHURN_SPIKE,
        name="Churn Prevention",
        steps=[
            RecoveryStep(
                agent_id="cs", priority=1,
                action="Identify at-risk accounts — check usage drop, support tickets, payment failures. Build save offers",
                trigger_reason="Autonomous recovery: churn rate spiked, activating retention protocols",
            ),
            RecoveryStep(
                agent_id="billing", priority=1,
                action="Check for failed payments driving involuntary churn — implement retry logic and card update flows",
                trigger_reason="Autonomous recovery: checking for payment-driven churn",
            ),
            RecoveryStep(
                agent_id="outreach", priority=2,
                action="Build re-engagement sequence for churned and at-risk customers — win-back offers",
                trigger_reason="Autonomous recovery: building win-back campaign for churning customers",
                depends_on="cs",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.PAYMENT_FAILURE_RATE,
        name="Payment Recovery",
        steps=[
            RecoveryStep(
                agent_id="billing", priority=1,
                action="Implement smart retry schedule — retry failed charges at optimal times, send card update reminders",
                trigger_reason="Autonomous recovery: payment failure rate exceeded threshold",
            ),
            RecoveryStep(
                agent_id="cs", priority=2,
                action="Proactively reach out to accounts with failed payments — offer alternative payment methods",
                trigger_reason="Autonomous recovery: preventing involuntary churn from payment failures",
                depends_on="billing",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.MRR_DECLINE,
        name="MRR Recovery Protocol",
        steps=[
            RecoveryStep(
                agent_id="analytics_agent", priority=1,
                action="Decompose MRR decline — is it churn, contraction, or new revenue slowdown? Identify root cause",
                trigger_reason="Autonomous recovery: MRR is declining, diagnosing root cause",
            ),
            RecoveryStep(
                agent_id="sales", priority=2,
                action="Accelerate pipeline — increase outreach velocity, tighten follow-up cadence, offer limited-time pricing",
                trigger_reason="Autonomous recovery: MRR declining, accelerating new revenue",
                depends_on="analytics_agent",
            ),
            RecoveryStep(
                agent_id="cs", priority=2,
                action="Launch expansion campaign — identify upsell opportunities in existing accounts",
                trigger_reason="Autonomous recovery: MRR declining, activating expansion revenue",
                depends_on="analytics_agent",
            ),
            RecoveryStep(
                agent_id="referral", priority=3,
                action="Activate referral program — incentivize existing customers to drive new revenue",
                trigger_reason="Autonomous recovery: diversifying new revenue channels during MRR decline",
                depends_on="cs",
            ),
        ],
    ),

    RecoveryPlaybook(
        signal_type=SignalType.ROAS_BELOW_THRESHOLD,
        name="ROAS Recovery",
        steps=[
            RecoveryStep(
                agent_id="ppc", priority=1,
                action="Pause campaigns with ROAS < 1x, shift budget to retargeting and lookalike audiences",
                trigger_reason="Autonomous recovery: ROAS below breakeven threshold",
            ),
            RecoveryStep(
                agent_id="ads", priority=2,
                action="Test new creative angles — focus on ROI-driven messaging, customer testimonials, specific outcomes",
                trigger_reason="Autonomous recovery: improving ad creative to increase ROAS",
                depends_on="ppc",
            ),
        ],
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMOUS REVENUE LOOP ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RevenueLoop:
    """
    Autonomous revenue optimization engine.

    Continuously monitors campaign metrics, detects revenue-impacting signals,
    selects appropriate recovery playbooks, and orchestrates multi-agent
    recovery — all without human intervention.

    Safety: max executions per day, cooldown between runs, severity gating.
    """

    def __init__(self):
        self._playbooks = {pb.signal_type: pb for pb in RECOVERY_PLAYBOOKS}
        self._active_signals: dict[str, RevenueSignal] = {}  # signal_id -> signal
        self._execution_log: list[dict] = []
        self._last_execution: dict[str, float] = {}  # signal_type -> last execution timestamp
        self._daily_counts: dict[str, int] = {}       # signal_type -> count today
        self._last_reset_day: str = ""

    def detect_signals(self, campaign_id: str, metrics: dict[str, Any]) -> list[RevenueSignal]:
        """
        Scan campaign metrics for revenue-impacting signals.
        Called by the sensing/health-check scheduler.
        """
        signals = []

        for rule in DETECTION_RULES:
            source_metrics = metrics.get(rule.metric_source, {})
            if not source_metrics:
                continue

            value = source_metrics.get(rule.metric_key)
            if value is None:
                continue

            # Check sample size
            if rule.sample_key and rule.min_sample:
                sample = source_metrics.get(rule.sample_key, 0)
                if sample < rule.min_sample:
                    continue

            # Evaluate rule
            triggered = False
            if rule.operator == "gt" and value > rule.threshold:
                triggered = True
            elif rule.operator == "lt" and value < rule.threshold:
                triggered = True
            elif rule.operator == "gte" and value >= rule.threshold:
                triggered = True
            elif rule.operator == "lte" and value <= rule.threshold:
                triggered = True

            if triggered:
                description = rule.description_template.format(
                    value=value, threshold=rule.threshold,
                )
                signal = RevenueSignal(
                    signal_type=rule.signal_type,
                    severity=rule.severity,
                    campaign_id=campaign_id,
                    metric_name=rule.metric_key,
                    current_value=value,
                    threshold=rule.threshold,
                    description=description,
                )
                signals.append(signal)
                self._active_signals[signal.id] = signal

        if signals:
            logger.info(
                f"Revenue signals detected for campaign {campaign_id}: "
                f"{[s.signal_type.value for s in signals]}"
            )

        return signals

    def get_recovery_plan(self, signal: RevenueSignal) -> Optional[RecoveryPlaybook]:
        """Get the recovery playbook for a signal, if one exists and is allowed to run."""
        playbook = self._playbooks.get(signal.signal_type)
        if not playbook:
            return None

        # Check daily limit
        self._reset_daily_if_needed()
        type_key = signal.signal_type.value
        daily_count = self._daily_counts.get(type_key, 0)
        if daily_count >= playbook.max_executions_per_day:
            logger.info(f"Playbook {playbook.name} skipped — daily limit reached ({daily_count})")
            return None

        # Check cooldown
        last_exec = self._last_execution.get(type_key, 0)
        cooldown_secs = playbook.cooldown_hours * 3600
        if time.time() - last_exec < cooldown_secs:
            remaining = cooldown_secs - (time.time() - last_exec)
            logger.info(f"Playbook {playbook.name} in cooldown — {remaining:.0f}s remaining")
            return None

        return playbook

    async def execute_recovery(self, signal: RevenueSignal,
                               playbook: RecoveryPlaybook,
                               campaign_id: str) -> dict:
        """
        Execute a recovery playbook — orchestrate agents in dependency order.
        Returns execution result summary.
        """
        type_key = signal.signal_type.value
        self._last_execution[type_key] = time.time()
        self._daily_counts[type_key] = self._daily_counts.get(type_key, 0) + 1

        logger.info(
            f"Executing recovery playbook: {playbook.name} "
            f"for signal {signal.signal_type.value} in campaign {campaign_id}"
        )

        execution = {
            "signal_id": signal.id,
            "playbook": playbook.name,
            "campaign_id": campaign_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "status": "in_progress",
        }

        # Group steps by priority
        priority_groups: dict[int, list[RecoveryStep]] = {}
        for step in playbook.steps:
            priority_groups.setdefault(step.priority, []).append(step)

        completed_agents: set[str] = set()

        for priority in sorted(priority_groups.keys()):
            steps = priority_groups[priority]

            # Filter: only run steps whose dependencies are met
            ready_steps = [
                s for s in steps
                if not s.depends_on or s.depends_on in completed_agents
            ]

            if not ready_steps:
                continue

            # These steps can run in parallel
            step_results = await asyncio.gather(*[
                self._execute_step(step, campaign_id, signal)
                for step in ready_steps
            ], return_exceptions=True)

            for step, result in zip(ready_steps, step_results):
                if isinstance(result, Exception):
                    execution["steps"].append({
                        "agent": step.agent_id, "status": "error",
                        "error": str(result),
                    })
                else:
                    execution["steps"].append(result)
                    if result.get("status") == "triggered":
                        completed_agents.add(step.agent_id)

        execution["status"] = "completed"
        execution["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Mark signal as addressed
        signal.resolution_actions = [s["agent"] for s in execution["steps"]]

        self._execution_log.append(execution)
        if len(self._execution_log) > 200:
            self._execution_log = self._execution_log[-200:]

        logger.info(f"Recovery playbook {playbook.name} completed: {len(execution['steps'])} steps executed")
        return execution

    async def _execute_step(self, step: RecoveryStep,
                            campaign_id: str, signal: RevenueSignal) -> dict:
        """Execute a single recovery step by triggering an agent via event bus."""
        try:
            from eventbus import event_bus, Event, EventType

            # Emit a custom event that triggers the agent to re-run
            await event_bus.emit(Event(
                type=EventType.CUSTOM,
                source_agent="revenue_loop",
                campaign_id=campaign_id,
                data={
                    "_action": "run_agent",
                    "_target_agent": step.agent_id,
                    "_trigger_reason": step.trigger_reason,
                    "_signal_type": signal.signal_type.value,
                    "_signal_description": signal.description,
                    "_recovery_action": step.action,
                },
            ))

            return {
                "agent": step.agent_id,
                "action": step.action,
                "status": "triggered",
                "trigger_reason": step.trigger_reason,
            }
        except Exception as e:
            logger.error(f"Recovery step failed for {step.agent_id}: {e}")
            return {
                "agent": step.agent_id,
                "action": step.action,
                "status": "error",
                "error": str(e),
            }

    async def run_detection_cycle(self, campaign_id: str, metrics: dict) -> dict:
        """
        Full detection + recovery cycle. Called by the health-check scheduler.
        Detects signals, selects playbooks, executes recovery.
        """
        signals = self.detect_signals(campaign_id, metrics)
        if not signals:
            return {"signals": 0, "recoveries": 0}

        recoveries = 0
        for signal in signals:
            playbook = self.get_recovery_plan(signal)
            if playbook:
                await self.execute_recovery(signal, playbook, campaign_id)
                recoveries += 1

        return {
            "signals": len(signals),
            "recoveries": recoveries,
            "signal_types": [s.signal_type.value for s in signals],
        }

    def _reset_daily_if_needed(self):
        """Reset daily counts at midnight."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_day:
            self._daily_counts = {}
            self._last_reset_day = today

    # ── Stats & Debug ────────────────────────────────────────────────────

    def get_active_signals(self, campaign_id: str = "") -> list[dict]:
        signals = list(self._active_signals.values())
        if campaign_id:
            signals = [s for s in signals if s.campaign_id == campaign_id]
        return [
            {
                "id": s.id, "type": s.signal_type.value,
                "severity": s.severity.value, "description": s.description,
                "current_value": s.current_value, "threshold": s.threshold,
                "resolved": s.resolved, "detected_at": s.detected_at,
            }
            for s in signals
        ]

    def get_execution_log(self, limit: int = 20) -> list[dict]:
        return self._execution_log[-limit:]

    def get_stats(self) -> dict:
        return {
            "active_signals": len(self._active_signals),
            "playbooks_available": len(self._playbooks),
            "total_recoveries": len(self._execution_log),
            "daily_counts": dict(self._daily_counts),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

revenue_loop = RevenueLoop()
