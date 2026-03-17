"""
Supervisor Backend — Background Job Scheduler
Runs periodic agent tasks: daily reports, weekly analytics, tax deadline alerts,
health checks, and genome learning sweeps.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
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
            now = datetime.utcnow()
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                if job.last_run is None or (now - job.last_run).total_seconds() >= job.interval_seconds:
                    asyncio.create_task(self._run_job(job))
            await asyncio.sleep(30)

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a single job with error handling."""
        job.last_run = datetime.utcnow()
        job.run_count += 1
        try:
            await job.handler()
            job.last_error = None
            logger.debug(f"Job {job.name} completed (run #{job.run_count})")
        except Exception as e:
            job.last_error = str(e)
            logger.error(f"Job {job.name} failed: {e}", exc_info=True)

    def get_status(self) -> list[dict[str, Any]]:
        return [{
            "name": j.name,
            "description": j.description,
            "interval_seconds": j.interval_seconds,
            "enabled": j.enabled,
            "last_run": j.last_run.isoformat() if j.last_run else None,
            "run_count": j.run_count,
            "last_error": j.last_error,
        } for j in self._jobs.values()]


# Singleton
scheduler = Scheduler()


# ── Built-in Job Handlers ──────────────────────────────────────────────────


async def _daily_finance_check():
    """Run finance health check across all active campaigns."""
    from main import campaigns
    from agents import get_agent
    from engine import engine

    agent = get_agent("finance")
    if not agent:
        return

    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        if not campaign.memory.financial_plan:
            continue
        try:
            async for event in engine.run(
                agent=agent, memory=campaign.memory,
                campaign_id=campaign_id, tier=Tier.FAST,
            ):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
            logger.info(f"Daily finance check complete for {campaign_id}")
        except Exception as e:
            logger.error(f"Daily finance check failed for {campaign_id}: {e}")


async def _weekly_analytics_sweep():
    """Run analytics agent across all active campaigns."""
    from main import campaigns
    from agents import get_agent
    from engine import engine

    agent = get_agent("analytics_agent")
    if not agent:
        return

    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        try:
            async for event in engine.run(
                agent=agent, memory=campaign.memory,
                campaign_id=campaign_id, tier=Tier.FAST,
            ):
                if event.memory_update:
                    for k, v in event.memory_update.items():
                        if hasattr(campaign.memory, k):
                            setattr(campaign.memory, k, v)
            logger.info(f"Weekly analytics sweep complete for {campaign_id}")
        except Exception as e:
            logger.error(f"Weekly analytics sweep failed for {campaign_id}: {e}")


async def _genome_learning_sweep():
    """Record DNA for all campaigns that don't have it yet."""
    from main import campaigns
    from genome import genome

    for campaign_id, campaign in list(campaigns.items()):
        if not genome.get_dna(campaign_id):
            genome.record_campaign_dna(campaign, getattr(campaign, '_metrics', {}))
            logger.info(f"Genome DNA recorded for {campaign_id}")


async def _tax_deadline_monitor():
    """Check upcoming tax deadlines and alert via campaign memory."""
    from main import campaigns

    now = datetime.utcnow()
    # Key US tax deadlines (month, day, description)
    deadlines = [
        (1, 15, "Q4 estimated tax payment due"),
        (1, 31, "W-2 and 1099-NEC filing deadline"),
        (3, 15, "S-Corp/Partnership returns due (1120-S/1065)"),
        (4, 15, "Individual/C-Corp returns due + Q1 estimated payment"),
        (6, 15, "Q2 estimated tax payment due"),
        (9, 15, "Q3 estimated tax payment due + S-Corp/Partnership extension deadline"),
        (10, 15, "Individual/C-Corp extension deadline"),
    ]

    for month, day, desc in deadlines:
        deadline_date = datetime(now.year, month, day)
        if deadline_date < now:
            deadline_date = datetime(now.year + 1, month, day)
        days_until = (deadline_date - now).days

        if days_until <= 30:
            for campaign in campaigns.values():
                if campaign.status == "active" and campaign.memory.tax_playbook:
                    logger.warning(f"Tax deadline alert for {campaign.id}: {desc} in {days_until} days")


async def _campaign_health_check():
    """Score all active campaigns, feed results to genome, and log failing agents."""
    from main import campaigns
    from scoring import scorer
    from genome import genome

    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        scores = scorer.score_all(campaign)

        # Feed scores back into genome DNA — closes the learning loop
        try:
            genome.record_scoring_outcomes(campaign, scores)
        except Exception as e:
            logger.error(f"Genome scoring feedback failed for {campaign_id}: {e}")

        failing = {aid: data for aid, data in scores.items()
                   if data.get("grade", "F") in ("D", "D-", "F")}
        if failing:
            agent_grades = ', '.join(f'{a}={d["grade"]}' for a, d in failing.items())
            logger.warning(
                f"Campaign {campaign_id} has {len(failing)} failing agents: {agent_grades}"
            )


async def _adaptation_refresh():
    """Refresh genome intelligence for active campaigns so agents stay current."""
    from main import campaigns
    from genome import genome

    refreshed = 0
    for campaign_id, campaign in list(campaigns.items()):
        if campaign.status != "active":
            continue
        try:
            recs = genome.get_recommendations(campaign)
            if recs.get("has_data"):
                intel_lines = [f"• {r}" for r in recs.get("recommendations", [])]
                benchmarks = recs.get("benchmarks", {})
                if benchmarks:
                    bench_strs = [f"{k}: {v}" for k, v in list(benchmarks.items())[:5]]
                    intel_lines.append(f"Benchmarks: {', '.join(bench_strs)}")
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
                       "Hourly genome DNA recording for new campaigns")
    scheduler.register("tax_deadlines", 86400, _tax_deadline_monitor,
                       "Daily tax deadline monitoring and alerts")
    scheduler.register("health_check", 21600, _campaign_health_check,
                       "6-hourly campaign health scoring check")
    scheduler.register("adaptation_refresh", 7200, _adaptation_refresh,
                       "2-hourly genome intelligence refresh for active campaigns")
