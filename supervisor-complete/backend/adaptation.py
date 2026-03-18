"""
Supervisor Backend — Adaptive Learning Engine
Closes the loop: sensing → scoring → genome → agent prompts.
Agents get smarter with every run based on real outcome data.

This is the moat — the more campaigns run, the smarter future campaigns start.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from models import Campaign

logger = logging.getLogger("supervisor.adaptation")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PerformanceFeedback:
    """What the data says about this agent's recent performance."""
    agent_id: str
    grade: str
    score: float
    reasoning: str
    key_metrics: dict[str, float] = field(default_factory=dict)
    trend: str = "unknown"  # "improving", "declining", "stable", "unknown"
    benchmark_delta: dict[str, float] = field(default_factory=dict)


@dataclass
class LearnedStrategy:
    """A specific behavioral directive derived from data."""
    source: str           # "scoring", "sensing", "genome", "lifecycle"
    directive: str        # natural language instruction for the agent
    confidence: float     # 0.0-1.0, based on data volume
    evidence: str = ""    # the data point supporting this


@dataclass
class AdaptiveContext:
    """The full adaptive injection for one agent run."""
    agent_id: str
    campaign_id: str
    performance: Optional[PerformanceFeedback] = None
    strategies: list[LearnedStrategy] = field(default_factory=list)
    genome_insights: dict[str, Any] = field(default_factory=dict)
    iteration_number: int = 1
    trigger_reason: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY RULES — Deterministic, not LLM-dependent
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StrategyRule:
    """A rule that fires when a metric condition is met."""
    agent_id: str
    condition: Any       # callable(PerformanceFeedback) -> bool
    directive: str       # template with {metric_name} placeholders
    source: str = "sensing"
    confidence: float = 0.8


# Rules organized by agent — these encode domain expertise about what to do
# when specific metrics are underperforming. This is NOT an LLM call.
STRATEGY_RULES: list[StrategyRule] = [
    # ── Outreach ──
    StrategyRule(
        agent_id="outreach",
        condition=lambda p: p.key_metrics.get("reply_rate", 100) < 2.0,
        directive=(
            "Reply rate is critically low at {reply_rate:.1f}%. Rewrite with: "
            "shorter subject lines (≤4 words), specific pain point in opening line, "
            "social proof by line 3, and a single clear CTA. Remove anything generic."
        ),
        confidence=0.9,
    ),
    StrategyRule(
        agent_id="outreach",
        condition=lambda p: p.key_metrics.get("open_rate", 100) < 30.0,
        directive=(
            "Open rate is {open_rate:.1f}% — below the 30% baseline. Test: "
            "question-based subjects, first-name personalization, lowercase subjects, "
            "number-based subjects (e.g., '3 ideas for {{company}}')."
        ),
        confidence=0.85,
    ),
    StrategyRule(
        agent_id="outreach",
        condition=lambda p: p.key_metrics.get("bounce_rate", 0) > 5.0,
        directive=(
            "Bounce rate is {bounce_rate:.1f}% — list quality issue. "
            "Verify emails before sending, remove role-based addresses (info@, sales@), "
            "and check domain health."
        ),
        confidence=0.95,
    ),

    # ── Content ──
    StrategyRule(
        agent_id="content",
        condition=lambda p: p.key_metrics.get("bounce_rate", 0) > 60.0,
        directive=(
            "Bounce rate is {bounce_rate:.1f}% — content doesn't match search intent. "
            "Restructure: answer the query in the first 100 words, add jump links, "
            "reduce intro length, use subheadings every 200 words."
        ),
        confidence=0.85,
    ),
    StrategyRule(
        agent_id="content",
        condition=lambda p: p.key_metrics.get("conversion_rate", 100) < 1.0 and p.key_metrics.get("sessions", 0) > 100,
        directive=(
            "Traffic is flowing ({sessions:.0f} sessions) but conversion is only {conversion_rate:.2f}%. "
            "Add inline CTAs after every major section, use exit-intent offers, "
            "and ensure the primary CTA is visible without scrolling."
        ),
        confidence=0.8,
    ),

    # ── Ads / PPC ──
    StrategyRule(
        agent_id="ads",
        condition=lambda p: p.key_metrics.get("cpa", 0) > 150.0,
        directive=(
            "CPA is ${cpa:.2f} — too high. Narrow audience targeting, pause broad match keywords, "
            "increase negative keywords, and test emotional vs logical ad copy variants."
        ),
        confidence=0.85,
    ),
    StrategyRule(
        agent_id="ads",
        condition=lambda p: p.key_metrics.get("ctr", 100) < 1.0 and p.key_metrics.get("impressions", 0) > 1000,
        directive=(
            "CTR is {ctr:.2f}% across {impressions:.0f} impressions — ads aren't compelling. "
            "Rewrite headlines with specific numbers and outcomes, use urgency triggers, "
            "and test image vs video creative."
        ),
        confidence=0.8,
    ),
    StrategyRule(
        agent_id="ppc",
        condition=lambda p: p.key_metrics.get("cpa", 0) > 150.0,
        directive=(
            "CPA is ${cpa:.2f}. Shift budget to top-performing ad groups, add "
            "negative keywords from search terms report, and test single-keyword ad groups."
        ),
        confidence=0.85,
    ),
    StrategyRule(
        agent_id="ppc",
        condition=lambda p: p.key_metrics.get("roas", 100) < 2.0 and p.key_metrics.get("spend", 0) > 500,
        directive=(
            "ROAS is {roas:.1f}x on ${spend:.0f} spend — below breakeven. "
            "Pause campaigns with ROAS < 1x, reallocate to retargeting, "
            "and test lookalike audiences from converted customers."
        ),
        confidence=0.85,
    ),

    # ── Social ──
    StrategyRule(
        agent_id="social",
        condition=lambda p: p.key_metrics.get("engagement_rate", 100) < 1.0 and p.key_metrics.get("posts", 0) > 10,
        directive=(
            "Engagement rate is {engagement_rate:.2f}% after {posts:.0f} posts — content isn't resonating. "
            "Shift to: personal stories, contrarian takes, ask-the-audience polls, "
            "and behind-the-scenes content. Reduce promotional posts to <20%."
        ),
        confidence=0.8,
    ),
    StrategyRule(
        agent_id="social",
        condition=lambda p: p.key_metrics.get("dms_received", 0) == 0 and p.key_metrics.get("posts", 0) > 15,
        directive=(
            "Zero DMs after {posts:.0f} posts — not driving conversations. "
            "End posts with direct questions, use 'DM me X' CTAs, "
            "and comment on prospect posts before expecting inbound."
        ),
        confidence=0.75,
    ),

    # ── Sales ──
    StrategyRule(
        agent_id="sales",
        condition=lambda p: p.key_metrics.get("close_rate", 100) < 15.0 and p.key_metrics.get("total_deals", 0) > 5,
        directive=(
            "Close rate is {close_rate:.1f}% across {total_deals:.0f} deals. "
            "Tighten qualification criteria, add discovery call scripts, "
            "implement mutual action plans, and follow up within 24h of every call."
        ),
        confidence=0.8,
    ),

    # ── Prospector ──
    StrategyRule(
        agent_id="prospector",
        condition=lambda p: p.key_metrics.get("total_deals", 0) == 0 and p.score < 50,
        directive=(
            "No prospects converting to meetings. Review ICP criteria — "
            "are we targeting the right titles, company sizes, and industries? "
            "Try narrowing to companies showing buying signals (hiring, funding, tech stack changes)."
        ),
        confidence=0.75,
    ),

    # ── Newsletter ──
    StrategyRule(
        agent_id="newsletter",
        condition=lambda p: p.key_metrics.get("open_rate", 100) < 25.0 and p.key_metrics.get("delivered", 0) > 50,
        directive=(
            "Newsletter open rate is {open_rate:.1f}%. "
            "Test: send time optimization, sender name personalization, "
            "curiosity-gap subject lines, and segment by engagement level."
        ),
        confidence=0.8,
    ),

    # ── Billing ──
    StrategyRule(
        agent_id="billing",
        condition=lambda p: p.key_metrics.get("collection_rate", 100) < 85.0,
        directive=(
            "Collection rate is {collection_rate:.1f}% — revenue leakage. "
            "Implement: automated 3-day pre-due reminders, failed payment retry sequence, "
            "offer alternative payment methods, and escalate 30+ day overdue to personal outreach."
        ),
        confidence=0.9,
    ),

    # ── CS ──
    StrategyRule(
        agent_id="cs",
        condition=lambda p: p.key_metrics.get("failed_payments", 0) > 3,
        directive=(
            "{failed_payments:.0f} failed payments detected — churn risk. "
            "Trigger proactive outreach to at-risk accounts, offer payment plan options, "
            "and ensure card expiration reminders are active."
        ),
        confidence=0.85,
    ),

    # ── Referral ──
    StrategyRule(
        agent_id="referral",
        condition=lambda p: p.key_metrics.get("customers", 0) > 5 and p.score < 40,
        directive=(
            "We have {customers:.0f} customers but referral program isn't producing. "
            "Launch NPS survey to identify promoters, offer 2-sided incentives, "
            "make sharing frictionless with pre-written referral messages."
        ),
        confidence=0.7,
    ),

    # ── Sitelaunch ──
    StrategyRule(
        agent_id="sitelaunch",
        condition=lambda p: p.key_metrics.get("bounce_rate", 0) > 70.0 and p.key_metrics.get("sessions", 0) > 50,
        directive=(
            "Site bounce rate is {bounce_rate:.1f}% — landing page needs work. "
            "Optimize: hero section must communicate value in ≤5 seconds, "
            "add social proof above fold, reduce form fields, improve page speed."
        ),
        confidence=0.85,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


# In-memory snapshot store (persisted to Supabase when available)
_run_snapshots: dict[str, list[dict]] = {}  # key: "{campaign_id}:{agent_id}"


class AdaptationEngine:
    """Builds adaptive context for agent runs based on real outcome data."""

    def build_context(
        self,
        agent_id: str,
        campaign: Campaign,
        trigger_reason: str = "",
    ) -> AdaptiveContext:
        """Assemble all available intelligence for this agent run."""
        from scoring import scorer
        from genome import genome

        ctx = AdaptiveContext(
            agent_id=agent_id,
            campaign_id=campaign.id,
            trigger_reason=trigger_reason,
        )

        # 1. Get current scores from scoring engine
        try:
            scores = scorer.score_all(campaign)
            agent_score = scores.get(agent_id, {})
            if agent_score and agent_score.get("grade", "—") != "—":
                # Get the metrics the scoring engine used
                scoring_metrics = agent_score.get("metrics", {})
                # Also pull raw sensing metrics
                raw_metrics = getattr(campaign, '_metrics', {})
                key_metrics = self._extract_agent_metrics(agent_id, raw_metrics, scoring_metrics)

                # Compute trend from snapshots
                trend = self._compute_trend(campaign.id, agent_id)

                # Get genome benchmarks for comparison
                benchmarks = self._get_benchmarks(campaign, genome)
                benchmark_delta = {}
                for k, v in key_metrics.items():
                    if k in benchmarks:
                        benchmark_delta[k] = round(v - benchmarks[k], 2)

                ctx.performance = PerformanceFeedback(
                    agent_id=agent_id,
                    grade=agent_score["grade"],
                    score=agent_score["score"],
                    reasoning=agent_score.get("reasoning", ""),
                    key_metrics=key_metrics,
                    trend=trend,
                    benchmark_delta=benchmark_delta,
                )
        except Exception as e:
            logger.warning(f"Scoring failed during adaptation for {agent_id}: {e}")

        # 2. Derive strategies from rules
        if ctx.performance:
            ctx.strategies = self._derive_strategies(agent_id, ctx.performance)

        # 3. Get genome intelligence (fresh, not stale)
        try:
            ctx.genome_insights = genome.get_live_intelligence(campaign)
        except Exception as e:
            logger.warning(f"Genome intelligence failed for {agent_id}: {e}")

        # 4. Add genome-derived strategies
        self._add_genome_strategies(ctx)

        # 5. Compute iteration number
        snap_key = f"{campaign.id}:{agent_id}"
        ctx.iteration_number = len(_run_snapshots.get(snap_key, [])) + 1

        return ctx

    def _extract_agent_metrics(
        self, agent_id: str, raw_metrics: dict, scoring_metrics: dict,
    ) -> dict[str, float]:
        """Pull the relevant metrics for this agent from sensing data."""
        # Map agent IDs to their primary metric sources
        metric_sources = {
            "outreach": "email_metrics",
            "newsletter": "email_metrics",
            "content": "site_metrics",
            "sitelaunch": "site_metrics",
            "social": "social_metrics",
            "ads": "ad_metrics",
            "ppc": "ad_metrics",
            "sales": "crm_metrics",
            "prospector": "crm_metrics",
            "billing": "billing_metrics",
            "cs": "revenue_metrics",
            "referral": "revenue_metrics",
        }

        source_key = metric_sources.get(agent_id)
        if source_key and source_key in raw_metrics:
            return {k: v for k, v in raw_metrics[source_key].items() if isinstance(v, (int, float))}

        # Fall back to scoring metrics
        return {k: v for k, v in scoring_metrics.items() if isinstance(v, (int, float))}

    def _compute_trend(self, campaign_id: str, agent_id: str) -> str:
        """Determine if this agent's performance is improving, declining, or stable."""
        snap_key = f"{campaign_id}:{agent_id}"
        snapshots = _run_snapshots.get(snap_key, [])

        if len(snapshots) < 2:
            return "unknown"

        # Compare last 2 scores
        recent = snapshots[-1]["score"]
        previous = snapshots[-2]["score"]

        if recent > previous + 5:
            return "improving"
        elif recent < previous - 5:
            return "declining"
        return "stable"

    def _get_benchmarks(self, campaign: Campaign, genome: Any) -> dict[str, float]:
        """Get genome benchmark averages for similar campaigns."""
        try:
            intel = genome.get_live_intelligence(campaign)
            return intel.get("avg_outcomes", {})
        except Exception:
            return {}

    def _derive_strategies(
        self, agent_id: str, performance: PerformanceFeedback,
    ) -> list[LearnedStrategy]:
        """Fire deterministic rules based on metric conditions."""
        strategies = []

        for rule in STRATEGY_RULES:
            if rule.agent_id != agent_id:
                continue
            try:
                if rule.condition(performance):
                    # Format the directive with actual metric values
                    directive = rule.directive.format(**performance.key_metrics)
                    strategies.append(LearnedStrategy(
                        source=rule.source,
                        directive=directive,
                        confidence=rule.confidence,
                        evidence=f"grade={performance.grade}, score={performance.score}",
                    ))
            except (KeyError, TypeError, ValueError):
                # Missing metric for this rule — skip it
                continue

        return strategies

    def _add_genome_strategies(self, ctx: AdaptiveContext) -> None:
        """Add strategies derived from cross-campaign genome data."""
        insights = ctx.genome_insights
        if not insights or insights.get("matches", 0) == 0:
            return

        # What worked in similar campaigns
        for lesson in insights.get("what_worked", [])[:3]:
            ctx.strategies.append(LearnedStrategy(
                source="genome",
                directive=f"Proven tactic from similar campaign: {lesson}",
                confidence=0.7,
                evidence=f"{insights['matches']} similar campaigns analyzed",
            ))

        # What didn't work — avoid these
        for lesson in insights.get("what_didnt", [])[:2]:
            ctx.strategies.append(LearnedStrategy(
                source="genome",
                directive=f"Avoid (failed in similar campaigns): {lesson}",
                confidence=0.65,
                evidence=f"{insights['matches']} similar campaigns analyzed",
            ))

    def render_prompt_block(self, ctx: AdaptiveContext) -> str:
        """Render the AdaptiveContext into a prompt block for injection."""
        if not ctx.performance and not ctx.strategies and not ctx.genome_insights.get("matches"):
            return ""  # First run, no data yet — don't inject anything

        lines: list[str] = []
        lines.append("═══ ADAPTIVE INTELLIGENCE (from real performance data) ═══")
        lines.append("")

        # Performance feedback
        if ctx.performance:
            p = ctx.performance
            lines.append(f"── YOUR PERFORMANCE (run #{ctx.iteration_number}) ──")
            lines.append(f"Grade: {p.grade} (score: {p.score:.0f}/100)")
            lines.append(f"Assessment: {p.reasoning}")

            if p.key_metrics:
                metric_strs = [f"{k}={v}" for k, v in list(p.key_metrics.items())[:6]]
                lines.append(f"Key metrics: {', '.join(metric_strs)}")

            if p.trend != "unknown":
                lines.append(f"Trend: {p.trend}")

            if p.benchmark_delta:
                deltas = []
                for k, v in p.benchmark_delta.items():
                    sign = "+" if v > 0 else ""
                    deltas.append(f"{k}: {sign}{v}")
                lines.append(f"vs. benchmark: {', '.join(deltas)}")

            lines.append("")

        # Learned strategies
        if ctx.strategies:
            lines.append("── STRATEGIES TO APPLY ──")
            # Sort by confidence
            sorted_strategies = sorted(ctx.strategies, key=lambda s: s.confidence, reverse=True)
            for i, s in enumerate(sorted_strategies[:5], 1):
                conf = "HIGH" if s.confidence >= 0.8 else "MEDIUM" if s.confidence >= 0.6 else "LOW"
                lines.append(f"{i}. [{conf}] {s.directive}")
            lines.append("")

        # Genome benchmarks
        benchmarks = ctx.genome_insights.get("avg_outcomes", {})
        if benchmarks:
            lines.append("── BENCHMARKS (from similar campaigns) ──")
            bench_strs = [f"{k}: {v}" for k, v in list(benchmarks.items())[:6]]
            lines.append(", ".join(bench_strs))
            lines.append("")

        # Trigger context
        if ctx.trigger_reason:
            lines.append(f"── WHY YOU'RE RE-RUNNING ──")
            lines.append(ctx.trigger_reason)
            lines.append("")

        # Directive
        if ctx.performance and ctx.performance.grade in ("C+", "C", "C-", "D", "D-", "F"):
            lines.append(
                "DIRECTIVE: Your previous output underperformed. Apply the strategies above. "
                "Be specific and actionable — generic advice will score poorly again."
            )
        elif ctx.performance and ctx.performance.trend == "improving":
            lines.append(
                "DIRECTIVE: Performance is improving. Double down on what's working "
                "and address any remaining weak metrics."
            )

        lines.append("═══════════════════════════════════════════════════════════")

        return "\n".join(lines)

    def record_run_snapshot(
        self,
        agent_id: str,
        campaign_id: str,
        score: float,
        metrics: dict[str, Any],
        strategies_applied: list[str] | None = None,
    ) -> dict:
        """Store a snapshot for trend computation and persist to database."""
        snap_key = f"{campaign_id}:{agent_id}"
        snapshots = _run_snapshots.setdefault(snap_key, [])

        snapshot = {
            "campaign_id": campaign_id,
            "agent_id": agent_id,
            "score": score,
            "metrics": metrics,
            "strategies_applied": strategies_applied or [],
            "iteration_number": len(snapshots) + 1,
            "created_at": datetime.utcnow().isoformat(),
        }

        snapshots.append(snapshot)

        # Keep only last 20 snapshots per agent per campaign
        if len(snapshots) > 20:
            _run_snapshots[snap_key] = snapshots[-20:]

        # Persist to database (non-blocking)
        try:
            import asyncio
            from db import save_run_snapshot
            asyncio.create_task(save_run_snapshot(snapshot))
        except Exception:
            pass  # Best-effort persistence

        logger.info(
            f"Snapshot recorded: {agent_id} in {campaign_id} — "
            f"score={score:.0f}, iteration={snapshot['iteration_number']}"
        )
        return snapshot

    async def load_snapshots_from_db(self, campaign_id: str, agent_id: str):
        """Hydrate in-memory snapshots from database on startup."""
        try:
            from db import load_run_snapshots
            snap_key = f"{campaign_id}:{agent_id}"
            if snap_key not in _run_snapshots:
                db_snapshots = await load_run_snapshots(campaign_id, agent_id, limit=20)
                if db_snapshots:
                    _run_snapshots[snap_key] = db_snapshots
                    logger.info(f"Loaded {len(db_snapshots)} snapshots for {agent_id} in {campaign_id}")
        except Exception as e:
            logger.debug(f"Failed to load snapshots from DB: {e}")


# Singleton
adaptation_engine = AdaptationEngine()
