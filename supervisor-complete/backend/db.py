"""
Supervisor Backend — Database Persistence Layer
Supabase-backed persistence for campaigns, agent runs, genome, wallet, and approvals.
Falls back to in-memory storage when Supabase is not configured.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Optional

from config import settings

logger = logging.getLogger("supervisor.db")

_client = None


def _get_client():
    """Lazy-init Supabase client."""
    global _client
    if _client is not None:
        return _client

    if not settings.supabase_url or not settings.supabase_service_key:
        logger.info("Supabase not configured — using in-memory storage")
        return None

    try:
        from supabase import create_client
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
        logger.info("Supabase client initialized")
        return _client
    except ImportError:
        logger.warning("supabase package not installed — using in-memory storage")
        return None
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        return None


def is_persistent() -> bool:
    """Check if we have a live database connection."""
    return _get_client() is not None


# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_campaign(campaign_id: str, user_id: str, memory: dict,
                        status: str = "active", profile_id: str = "") -> bool:
    """Upsert a campaign to the database."""
    client = _get_client()
    if not client:
        return False

    try:
        data = {
            "id": campaign_id,
            "user_id": user_id,
            "status": status,
            "memory": json.dumps(memory) if isinstance(memory, dict) else memory,
        }
        if profile_id:
            data["profile_id"] = profile_id

        client.table("campaigns").upsert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save campaign {campaign_id}: {e}")
        return False


async def load_campaign(campaign_id: str) -> Optional[dict]:
    """Load a campaign from the database."""
    client = _get_client()
    if not client:
        return None

    try:
        result = client.table("campaigns").select("*").eq("id", campaign_id).single().execute()
        return result.data
    except Exception as e:
        logger.error(f"Failed to load campaign {campaign_id}: {e}")
        return None


async def load_user_campaigns(user_id: str) -> list[dict]:
    """Load all campaigns for a user."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("campaigns")
                  .select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load campaigns for user {user_id}: {e}")
        return []


async def update_campaign_memory(campaign_id: str, memory: dict) -> bool:
    """Update just the memory JSONB for a campaign."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("campaigns").update({
            "memory": json.dumps(memory) if isinstance(memory, dict) else memory,
        }).eq("id", campaign_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update campaign memory {campaign_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT RUNS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_agent_run(run: dict) -> bool:
    """Save an agent run record."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("agent_runs").upsert(run).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save agent run: {e}")
        return False


async def load_agent_runs(campaign_id: str) -> list[dict]:
    """Load all agent runs for a campaign."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("agent_runs")
                  .select("*")
                  .eq("campaign_id", campaign_id)
                  .order("started_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load agent runs for {campaign_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# SPEND LOG
# ═══════════════════════════════════════════════════════════════════════════════

async def save_spend_entry(entry: dict) -> bool:
    """Save a spend log entry."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("spend_log").insert(entry).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save spend entry: {e}")
        return False


async def load_spend_log(campaign_id: str, agent_id: str = "") -> list[dict]:
    """Load spend log entries."""
    client = _get_client()
    if not client:
        return []

    try:
        query = client.table("spend_log").select("*").eq("campaign_id", campaign_id)
        if agent_id:
            query = query.eq("agent_id", agent_id)
        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load spend log for {campaign_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN GENOME
# ═══════════════════════════════════════════════════════════════════════════════

async def save_genome_dna(dna: dict) -> bool:
    """Save campaign genome DNA."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("campaign_genome").upsert(dna).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save genome DNA: {e}")
        return False


async def load_all_genome_dna() -> list[dict]:
    """Load all genome DNA entries for cross-campaign intelligence."""
    client = _get_client()
    if not client:
        return []

    try:
        result = client.table("campaign_genome").select("*").execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load genome DNA: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

async def save_approval(item: dict) -> bool:
    """Save an approval queue item."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("approval_queue").upsert(item).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save approval: {e}")
        return False


async def load_approvals(status: str = "pending") -> list[dict]:
    """Load approval queue items by status."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("approval_queue")
                  .select("*")
                  .eq("status", status)
                  .order("created_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load approvals: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_performance_event(event: dict) -> bool:
    """Save a performance event from webhooks."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("performance_events").insert(event).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save performance event: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

async def save_onboarding_profile(profile: dict) -> bool:
    """Save onboarding profile."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("onboarding_profiles").upsert(profile).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save onboarding profile: {e}")
        return False


async def load_onboarding_profile(profile_id: str) -> Optional[dict]:
    """Load an onboarding profile."""
    client = _get_client()
    if not client:
        return None

    try:
        result = (client.table("onboarding_profiles")
                  .select("*")
                  .eq("id", profile_id)
                  .single()
                  .execute())
        return result.data
    except Exception as e:
        logger.error(f"Failed to load onboarding profile {profile_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# BUDGET
# ═══════════════════════════════════════════════════════════════════════════════

async def save_budget(campaign_id: str, agent_id: str, allocated: float,
                      spent: float, period: str = "monthly") -> bool:
    """Upsert agent budget allocation."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("agent_budgets").upsert({
            "campaign_id": campaign_id,
            "agent_id": agent_id,
            "allocated": allocated,
            "spent": spent,
            "period": period,
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save budget: {e}")
        return False


async def load_budgets(campaign_id: str) -> list[dict]:
    """Load all budget allocations for a campaign."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("agent_budgets")
                  .select("*")
                  .eq("campaign_id", campaign_id)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load budgets for {campaign_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT RUN SNAPSHOTS (for adaptive learning trends)
# ═══════════════════════════════════════════════════════════════════════════════

async def save_run_snapshot(snapshot: dict) -> bool:
    """Save an agent run snapshot for trend analysis."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("agent_run_snapshots").insert(snapshot).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save run snapshot: {e}")
        return False


async def load_run_snapshots(
    campaign_id: str, agent_id: str, limit: int = 10,
) -> list[dict]:
    """Load recent run snapshots for trend computation."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("agent_run_snapshots")
                  .select("*")
                  .eq("campaign_id", campaign_id)
                  .eq("agent_id", agent_id)
                  .order("created_at", desc=True)
                  .limit(limit)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load run snapshots: {e}")
        return []
