"""
Omni OS Backend — Database Persistence Layer
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


async def load_all_campaigns(user_id: str) -> list:
    """Fetch all campaigns for a user from Supabase and return as Campaign objects."""
    from models import Campaign, CampaignMemory, BusinessProfile
    rows = await load_user_campaigns(user_id)
    campaigns_out = []
    for row in rows:
        try:
            memory_raw = row.get("memory", {})
            if isinstance(memory_raw, str):
                memory_raw = json.loads(memory_raw)

            # Reconstruct BusinessProfile from stored memory
            biz_data = memory_raw.get("business", {})
            biz = BusinessProfile(**biz_data) if biz_data else BusinessProfile(
                name="", service="", icp="", geography="", goal=""
            )

            # Build CampaignMemory from stored fields
            mem_fields = {k: v for k, v in memory_raw.items() if k != "business" and not k.startswith("has_")}
            mem = CampaignMemory(business=biz, **{
                k: v for k, v in mem_fields.items()
                if hasattr(CampaignMemory, k) and k != "business"
            })

            campaign = Campaign(
                id=row["id"],
                user_id=row.get("user_id", user_id),
                memory=mem,
                status=row.get("status", "active"),
            )
            # Preserve created_at from DB if present
            if row.get("created_at"):
                try:
                    from datetime import datetime as _dt
                    campaign.created_at = _dt.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                except Exception:
                    pass
            campaigns_out.append(campaign)
        except Exception as e:
            logger.error(f"Failed to reconstruct campaign {row.get('id', '?')}: {e}")
            continue
    return campaigns_out


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
# EVENT BUS EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_event(event: dict) -> bool:
    """Persist an event bus event to the events table."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("events").insert({
            "id": event.get("id", ""),
            "event_type": event.get("type", ""),
            "source_agent": event.get("source_agent", ""),
            "campaign_id": event.get("campaign_id", ""),
            "data": json.dumps(event.get("data", {})),
            "created_at": event.get("timestamp", datetime.utcnow().isoformat()),
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save event: {e}")
        return False


async def load_events(campaign_id: str = "", event_type: str = "",
                      limit: int = 100) -> list[dict]:
    """Load recent events from the events table."""
    client = _get_client()
    if not client:
        return []

    try:
        query = client.table("events").select("*").order("created_at", desc=True).limit(limit)
        if campaign_id:
            query = query.eq("campaign_id", campaign_id)
        if event_type:
            query = query.eq("event_type", event_type)
        result = query.execute()
        rows = result.data or []
        # Deserialize data JSON
        for row in rows:
            if isinstance(row.get("data"), str):
                try:
                    row["data"] = json.loads(row["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return rows
    except Exception as e:
        logger.error(f"Failed to load events: {e}")
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


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT CHECKPOINTS (mid-execution state snapshots)
# ═══════════════════════════════════════════════════════════════════════════════

async def save_checkpoint(checkpoint: dict) -> bool:
    """Persist an agent checkpoint to the database."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("agent_checkpoints").upsert({
            "id": checkpoint.get("checkpoint_id", ""),
            "trace_id": checkpoint.get("trace_id", ""),
            "agent_id": checkpoint.get("agent_id", ""),
            "campaign_id": checkpoint.get("campaign_id", ""),
            "step_number": checkpoint.get("step_number", 0),
            "state": json.dumps({
                "messages_so_far": checkpoint.get("messages_so_far", []),
                "memory_so_far": checkpoint.get("memory_so_far", {}),
                "tool_results_so_far": checkpoint.get("tool_results_so_far", []),
                "system_prompt": checkpoint.get("system_prompt", ""),
                "full_text_output": checkpoint.get("full_text_output", ""),
            }),
            "created_at": checkpoint.get("timestamp", datetime.utcnow().isoformat()),
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")
        return False


async def load_checkpoints(agent_id: str, campaign_id: str = "",
                           limit: int = 50) -> list[dict]:
    """Load checkpoints for an agent, optionally filtered by campaign."""
    client = _get_client()
    if not client:
        return []

    try:
        query = (client.table("agent_checkpoints")
                 .select("*")
                 .eq("agent_id", agent_id)
                 .order("created_at", desc=True)
                 .limit(limit))
        if campaign_id:
            query = query.eq("campaign_id", campaign_id)
        result = query.execute()
        rows = result.data or []
        # Deserialize state JSON
        for row in rows:
            if isinstance(row.get("state"), str):
                try:
                    row["state"] = json.loads(row["state"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return rows
    except Exception as e:
        logger.error(f"Failed to load checkpoints for {agent_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# DEVELOPER PLATFORM — API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_api_key(record: dict) -> bool:
    """Persist a developer API key record."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_api_keys").upsert(record).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save API key {record.get('id', '?')}: {e}")
        return False


async def get_api_keys(user_id: str) -> list[dict]:
    """Load all API key records for a user."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("developer_api_keys")
                  .select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load API keys for user {user_id}: {e}")
        return []


async def delete_api_key(key_id: str) -> bool:
    """Delete an API key record from the database."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_api_keys").delete().eq("id", key_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete API key {key_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# DEVELOPER PLATFORM — WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_webhook(subscription: dict) -> bool:
    """Persist a webhook subscription."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_webhooks").upsert(subscription).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save webhook {subscription.get('id', '?')}: {e}")
        return False


async def get_webhooks(user_id: str) -> list[dict]:
    """Load all webhook subscriptions for a user."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("developer_webhooks")
                  .select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load webhooks for user {user_id}: {e}")
        return []


async def delete_webhook(wh_id: str) -> bool:
    """Delete a webhook subscription from the database."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_webhooks").delete().eq("id", wh_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete webhook {wh_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# DEVELOPER PLATFORM — OAUTH APPS
# ═══════════════════════════════════════════════════════════════════════════════

async def save_oauth_app(app: dict) -> bool:
    """Persist an OAuth application."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_oauth_apps").upsert(app).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save OAuth app {app.get('id', '?')}: {e}")
        return False


async def get_oauth_apps(user_id: str) -> list[dict]:
    """Load all OAuth apps for a user."""
    client = _get_client()
    if not client:
        return []

    try:
        result = (client.table("developer_oauth_apps")
                  .select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load OAuth apps for user {user_id}: {e}")
        return []


async def delete_oauth_app(app_id: str) -> bool:
    """Delete an OAuth application from the database."""
    client = _get_client()
    if not client:
        return False

    try:
        client.table("developer_oauth_apps").delete().eq("id", app_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete OAuth app {app_id}: {e}")
        return False
