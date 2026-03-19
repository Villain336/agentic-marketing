"""
Omni OS Backend — Background Job Scheduler
Runs periodic agent tasks: daily reports, weekly analytics, tax deadline alerts,
health checks, and genome learning sweeps.

All job handlers do real work: score campaigns, feed results to genome,
trigger agent re-runs on failure, and persist tax alerts.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

from models import Campaign, CampaignMemory, Tier

logger = logging.getLogger("supervisor.scheduler")


class ScheduledJob:
    """A single recurring job definition."""

    def __init__(
        self,
        name: str,
        interval_seconds: int,
        handler: Callable[..., Coroutine],
        description: str = "",
        enabled: bool = True,
    ):
        self.name = name
        self.interval_seconds = interval_seconds
        self.handler = handler
        self.description = description
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.run_count: int = 0
        self.last_error: str | None = None
        self.last_duration: float = 0.0
        self.consecutive_failures: int = 0


class Scheduler:
    """Background job scheduler that runs alongside the FastAPI event loop."""

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register(self, name: str, interval_seconds: int,
                 handler: Callable, description: str = "") -> None:
        self._jobs[name] = ScheduledJob(
            name=name, interval_seconds=interval_seconds,
            handler=handler, description=description,
        )
        logger.info(f"Registered job: {name} (every {interval_seconds}s)")

    def unregister(self, name: str) -> bool:
        if name in self._jobs:
            del self._jobs[name]
            return True
        return False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Scheduler started with {len(self._jobs)} jobs")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Main scheduler loop — checks jobs every 30 seconds."""
        while self._running:
            now = datetime.now(timezone.utc)
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                if job.last_run is None or (now - job.last_run).total_seconds() >= job.interval_seconds:
                    asyncio.create_task(self._run_job(job))
            await asyncio.sleep(30)

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a single job with error handling and timing."""
        job.last_run = datetime.now(timezone.utc)
        job.run_count += 1
        start = asyncio.get_event_loop().time()
        try:
            await job.handler()
            job.last_error = None
            job.consecutive_failures = 0
            job.last_duration = round(asyncio.get_event_loop().time() - start, 2)
            logger.debug(f"Job {job.name} completed in {job.last_duration}s (run #{job.run_count})")
        except Exception as e:
            job.last_error = str(e)
            job.consecutive_failures += 1
            job.last_duration = round(asyncio.get_event_loop().time() - start, 2)
            logger.error(f"Job {job.name} failed (attempt #{job.consecutive_failures}): {e}", exc_info=True)

            # If a job fails 3+ times in a row, disable it and alert
            if job.consecutive_failures >= 3:
                job.enabled = False
                logger.critical(
                    f"Job {job.name} disabled after {job.consecutive_failures} consecutive failures. "
                    f"Last error: {e}"
                )

    def get_status(self) -> list[dict[str, Any]]:
        return [{
            "name": j.name,
            "description": j.description,
            "interval_seconds": j.interval_seconds,
            "enabled": j.enabled,
            "last_run": j.last_run.isoformat() if j.last_run else None,
            "run_count": j.run_count,
            "last_error": j.last_error,
            "last_duration": j.last_duration,
            "consecutive_failures": j.consecutive_failures,
        } for j in self._jobs.values()]

    def reset_job(self, name: str) -> bool:
        """Re-enable a disabled job and reset its failure counter."""
        job = self._jobs.get(name)
        if not job:
            return False
        job.enabled = True
        job.consecutive_failures = 0
        job.last_error = None
        return True


# Singleton
scheduler = Scheduler()


# ── Built-in Job Handlers ──────────────────────────────────────────────────


async def _daily_finance_check():
    """Run finance health check across all active campaigns.

    Actually runs the finance agent and applies memory updates so
    financial_plan stays current with latest payment data.
    """
    from main import campaigns
    from agents import get_agent
    from engine import engine
    from sensing import sensing

    agent = get_agent("finance")
    if not agent:
        logger.warning("Finance agent not found — skipping daily finance check")
        return

    checked = 0
    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        if not campaign.memory.financial_plan:
            continue

        # Ensure sensing metrics are loaded before running the agent
        await sensing.load_metrics_from_db(campaign)

        try:
            async for event in engine.run(
                agent=agent, memory=campaign.memory,
                campaign_id=campaign_id, tier=Tier.FAST,
            ):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
            checked += 1
            logger.info(f"Daily finance check complete for {campaign_id}")
        except Exception as e:
            logger.error(f"Daily finance check failed for {campaign_id}: {e}")

    logger.info(f"Daily finance check: processed {checked} campaigns")


async def _weekly_analytics_sweep():
    """Run analytics agent across all active campaigns.

    Loads sensing metrics first so the analytics agent has real data
    to analyze, not empty dicts.
    """
    from main import campaigns
    from agents import get_agent
    from engine import engine
    from sensing import sensing

    agent = get_agent("analytics_agent")
    if not agent:
        logger.warning("Analytics agent not found — skipping weekly sweep")
        return

    swept = 0
    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue

        # Load real metrics from DB
        await sensing.load_metrics_from_db(campaign)

        try:
            async for event in engine.run(
                agent=agent, memory=campaign.memory,
                campaign_id=campaign_id, tier=Tier.FAST,
            ):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
            swept += 1
            logger.info(f"Weekly analytics sweep complete for {campaign_id}")
        except Exception as e:
            logger.error(f"Weekly analytics sweep failed for {campaign_id}: {e}")

    logger.info(f"Weekly analytics sweep: processed {swept} campaigns")


async def _genome_learning_sweep():
    """Record DNA for all campaigns, using real sensing metrics.

    Feeds actual accumulated metrics (from sensing webhooks) into genome
    DNA so cross-campaign intelligence is based on real performance data.
    """
    from main import campaigns
    from genome import genome
    from sensing import sensing

    # Ensure genome DB is loaded
    await genome.load_from_db()

    recorded = 0
    updated = 0
    for campaign_id, campaign in list(campaigns.items()):
        # Load sensing metrics from DB
        await sensing.load_metrics_from_db(campaign)
        raw_metrics = getattr(campaign, '_metrics', {})

        # Flatten sensing metrics into a single dict for genome
        flat_metrics: dict[str, Any] = {}
        for source_key, source_data in raw_metrics.items():
            if isinstance(source_data, dict):
                for k, v in source_data.items():
                    if isinstance(v, (int, float)):
                        flat_metrics[k] = v

        existing = genome.get_dna(campaign_id)
        if not existing:
            await genome.record_campaign_dna(campaign, flat_metrics)
            recorded += 1
        elif flat_metrics:
            # Update existing DNA with latest metrics
            await genome.update_outcomes(campaign_id, {k: v for k, v in flat_metrics.items() if isinstance(v, (int, float))})
            updated += 1

    logger.info(f"Genome sweep: recorded {recorded} new, updated {updated} existing")


async def _tax_deadline_monitor():
    """Check upcoming tax deadlines and write alerts into campaign memory.

    Actually persists deadline alerts so they surface in agent context,
    and triggers the tax agent to re-run when deadlines are imminent.
    """
    from main import campaigns
    from agents import get_agent
    from engine import engine

    now = datetime.now(timezone.utc)
    # Key US tax deadlines (month, day, description, urgency_days)
    deadlines = [
        (1, 15, "Q4 estimated tax payment due", 14),
        (1, 31, "W-2 and 1099-NEC filing deadline", 21),
        (3, 15, "S-Corp/Partnership returns due (1120-S/1065)", 21),
        (4, 15, "Individual/C-Corp returns due + Q1 estimated payment", 30),
        (6, 15, "Q2 estimated tax payment due", 14),
        (9, 15, "Q3 estimated tax payment due + S-Corp/Partnership extension deadline", 21),
        (10, 15, "Individual/C-Corp extension deadline", 21),
    ]

    alerts_issued = 0
    for month, day, desc, urgency_days in deadlines:
        try:
            deadline_date = datetime(now.year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        if deadline_date < now:
            deadline_date = datetime(now.year + 1, month, day, tzinfo=timezone.utc)
        days_until = (deadline_date - now).days

        if days_until <= urgency_days:
            urgency = "CRITICAL" if days_until <= 7 else "WARNING" if days_until <= 14 else "UPCOMING"

            for campaign_id, campaign in list(campaigns.items()):
                if campaign.status != "active":
                    continue
                if not campaign.memory.tax_playbook:
                    continue

                # Build alert and append to tax_playbook so agents see it
                alert = f"\n\n[{urgency}] {desc} — {days_until} days remaining (due {deadline_date.strftime('%B %d, %Y')})"
                if alert not in (campaign.memory.tax_playbook or ""):
                    campaign.memory.tax_playbook = (campaign.memory.tax_playbook or "") + alert
                    alerts_issued += 1
                    logger.warning(f"Tax alert for {campaign_id}: {desc} in {days_until} days")

                    # If critical (<=7 days), trigger the tax agent to re-run
                    if days_until <= 7:
                        tax_agent = get_agent("tax")
                        if tax_agent:
                            try:
                                async for event in engine.run(
                                    agent=tax_agent, memory=campaign.memory,
                                    campaign_id=campaign_id, tier=Tier.FAST,
                                ):
                                    if event.memory_update:
                                        for k, v in event.memory_update.items():
                                            if hasattr(campaign.memory, k):
                                                setattr(campaign.memory, k, v)
                                logger.info(f"Tax agent re-run triggered for {campaign_id} (deadline in {days_until} days)")
                            except Exception as e:
                                logger.error(f"Tax agent re-run failed for {campaign_id}: {e}")

    if alerts_issued:
        logger.info(f"Tax deadline monitor: issued {alerts_issued} alerts")


async def _campaign_health_check():
    """Score all active campaigns, feed results to genome, trigger re-runs for failing agents.

    This is the central feedback loop:
    1. Load sensing metrics from DB
    2. Score all agents
    3. Record snapshots for trend tracking
    4. Feed scores to genome for cross-campaign learning
    5. Trigger re-runs for agents graded D or F
    """
    from main import campaigns
    from scoring import scorer
    from genome import genome
    from adaptation import adaptation_engine
    from sensing import sensing
    from agents import get_agent
    from engine import engine

    # Ensure genome is loaded
    await genome.load_from_db()

    total_checked = 0
    total_failing = 0
    total_rerun = 0

    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue

        # 1. Load real sensing metrics
        await sensing.load_metrics_from_db(campaign)

        # 2. Score all agents
        scores = scorer.score_all(campaign)
        total_checked += 1

        # 3. Record adaptation snapshots for each scored agent
        for agent_id, data in scores.items():
            if data.get("grade", "—") == "—":
                continue
            try:
                await adaptation_engine.record_run_snapshot(
                    agent_id=agent_id,
                    campaign_id=campaign_id,
                    score=data.get("score", 0),
                    metrics=data.get("metrics", {}),
                )
            except Exception as e:
                logger.error(f"Snapshot recording failed for {agent_id}/{campaign_id}: {e}")

        # 4. Feed scores to genome for cross-campaign learning
        try:
            await genome.record_scoring_outcomes(campaign, scores)
        except Exception as e:
            logger.error(f"Genome scoring feedback failed for {campaign_id}: {e}")

        # 5. Identify and re-run failing agents
        failing = {aid: data for aid, data in scores.items()
                   if data.get("grade", "F") in ("D", "D-", "F")}

        if failing:
            total_failing += len(failing)
            agent_grades = ', '.join(f'{a}={d["grade"]}' for a, d in failing.items())
            logger.warning(f"Campaign {campaign_id} has {len(failing)} failing agents: {agent_grades}")

            # Re-run each failing agent with adaptive context
            for agent_id, data in failing.items():
                agent = get_agent(agent_id)
                if not agent:
                    continue

                # Build adaptive context with performance feedback
                try:
                    ctx = await adaptation_engine.build_context(
                        agent_id=agent_id,
                        campaign=campaign,
                        trigger_reason=f"Health check: {agent_id} scored {data['grade']} ({data.get('score', 0):.0f}/100)",
                    )
                    prompt_block = adaptation_engine.render_prompt_block(ctx)

                    # Inject adaptive context into agent memory for this run
                    if prompt_block:
                        campaign.memory.genome_intel = prompt_block

                    async for event in engine.run(
                        agent=agent, memory=campaign.memory,
                        campaign_id=campaign_id, tier=Tier.FAST,
                    ):
                        if event.memory_update:
                            for k, v in event.memory_update.items():
                                if hasattr(campaign.memory, k):
                                    setattr(campaign.memory, k, v)

                    total_rerun += 1
                    logger.info(f"Re-ran failing agent {agent_id} for {campaign_id} (was {data['grade']})")
                except Exception as e:
                    logger.error(f"Failed to re-run {agent_id} for {campaign_id}: {e}")

    logger.info(
        f"Health check complete: {total_checked} campaigns scored, "
        f"{total_failing} failing agents found, {total_rerun} agents re-run"
    )


async def _adaptation_refresh():
    """Refresh genome intelligence and adaptive context for active campaigns.

    Updates genome_intel in campaign memory with latest cross-campaign
    intelligence so subsequent agent runs benefit from fresh data.
    Also loads latest snapshots so trend computation is current.
    """
    from main import campaigns
    from genome import genome
    from adaptation import adaptation_engine
    from sensing import sensing

    # Ensure genome is loaded
    await genome.load_from_db()

    refreshed = 0
    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        try:
            # Load sensing metrics so recommendations are data-informed
            await sensing.load_metrics_from_db(campaign)

            # Load adaptation snapshots for all agents
            await adaptation_engine.load_all_snapshots_for_campaign(campaign_id)

            # Get genome recommendations
            recs = genome.get_recommendations(campaign)
            if recs.get("has_data"):
                intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
                benchmarks = recs.get("benchmarks", {})
                if benchmarks:
                    bench_strs = [f"{k}: {v}" for k, v in list(benchmarks.items())[:5]]
                    intel_lines.append(f"Benchmarks: {', '.join(bench_strs)}")

                matches = recs.get("matches", 0)
                intel_lines.insert(0, f"[Genome: {matches} similar campaigns analyzed]")

                campaign.memory.genome_intel = "\n".join(intel_lines)
                refreshed += 1
        except Exception as e:
            logger.error(f"Adaptation refresh failed for {campaign_id}: {e}")

    if refreshed:
        logger.info(f"Adaptation refresh: updated genome intel for {refreshed} campaigns")


def register_default_jobs():
    """Register all built-in scheduled jobs."""
    scheduler.register("daily_finance", 86400, _daily_finance_check,
                       "Daily finance health check across active campaigns")
    scheduler.register("weekly_analytics", 604800, _weekly_analytics_sweep,
                       "Weekly analytics sweep across active campaigns")
    scheduler.register("genome_sweep", 3600, _genome_learning_sweep,
                       "Hourly genome DNA recording with real sensing metrics")
    scheduler.register("tax_deadlines", 86400, _tax_deadline_monitor,
                       "Daily tax deadline monitoring with critical alerts triggering agent re-runs")
    scheduler.register("health_check", 21600, _campaign_health_check,
                       "6-hourly campaign health scoring with adaptive re-runs for failing agents")
    scheduler.register("adaptation_refresh", 7200, _adaptation_refresh,
                       "2-hourly genome intelligence refresh with snapshot hydration")
