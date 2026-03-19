"""Autonomy settings, agent settings, event bus triggers."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from autonomy import autonomy_store, AgentAutonomySettings
from eventbus import event_bus, EventType, TriggerRule
from auth import get_user_id, validate_id
import db

logger = logging.getLogger("supervisor.api.settings")

router = APIRouter(tags=["Settings"])


# ── Request Models ────────────────────────────────────────────────────────

AUTONOMY_WRITABLE_FIELDS = {
    "global_level", "spending_approval_threshold",
    "outbound_approval_required", "content_approval_required",
    "infrastructure_approval_required", "escalation_channel",
}

AGENT_SETTINGS_WRITABLE_FIELDS = {
    "autonomy_level", "spending_limit", "approval_required",
    "enabled", "max_iterations", "timeout",
}


class AutonomySettingsUpdate(BaseModel):
    global_level: Optional[str] = None
    spending_approval_threshold: Optional[float] = None
    outbound_approval_required: Optional[bool] = None
    content_approval_required: Optional[bool] = None
    infrastructure_approval_required: Optional[bool] = None
    escalation_channel: Optional[str] = None


class TriggerCreate(BaseModel):
    event_type: str
    name: str = ""
    action: str = ""
    condition: Optional[dict] = None
    target: Optional[dict] = None
    enabled: bool = True


# ── Autonomy Settings ────────────────────────────────────────────────────

@router.get("/settings/autonomy")
async def get_autonomy_settings(request: Request, campaign_id: str = ""):
    """Get current autonomy settings (global or per-campaign)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")
    return autonomy_store.to_dict(campaign_id)


@router.put("/settings/autonomy")
async def update_autonomy_settings(request: Request, campaign_id: str = ""):
    """Update autonomy settings (global or per-campaign)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")

    body = await request.json()
    current = autonomy_store.get(campaign_id)

    for field_name in AUTONOMY_WRITABLE_FIELDS:
        if field_name in body:
            setattr(current, field_name, body[field_name])

    if campaign_id:
        autonomy_store.set(campaign_id, current)
    else:
        autonomy_store.set_global(current)

    return autonomy_store.to_dict(campaign_id)


@router.get("/settings/agents")
async def get_all_agent_settings(request: Request, campaign_id: str = ""):
    """Get per-agent autonomy settings."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")
    return autonomy_store.get_all_agent_settings(campaign_id)


@router.get("/settings/agents/{agent_id}")
async def get_agent_settings(agent_id: str, request: Request, campaign_id: str = ""):
    """Get autonomy settings for a specific agent."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(agent_id, "agent_id")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")

    settings_obj = autonomy_store.get(campaign_id)
    agent_cfg = settings_obj.per_agent.get(agent_id)
    if agent_cfg:
        return agent_cfg.model_dump()
    return AgentAutonomySettings(agent_id=agent_id).model_dump()


@router.put("/settings/agents/{agent_id}")
async def update_agent_settings(agent_id: str, request: Request, campaign_id: str = ""):
    """Update autonomy settings for a specific agent."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(agent_id, "agent_id")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")

    body = await request.json()
    filtered = {k: v for k, v in body.items() if k in AGENT_SETTINGS_WRITABLE_FIELDS}
    agent_cfg = autonomy_store.update_agent(campaign_id, agent_id, filtered)
    return agent_cfg.model_dump()


@router.post("/settings/agents/batch")
async def batch_update_agent_settings(request: Request, campaign_id: str = ""):
    """Batch update settings for multiple agents at once."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Expected a JSON object mapping agent_id to settings")

    results = {}
    for agent_id, updates in body.items():
        validate_id(agent_id, "agent_id")
        if not isinstance(updates, dict):
            continue
        filtered = {k: v for k, v in updates.items() if k in AGENT_SETTINGS_WRITABLE_FIELDS}
        agent_cfg = autonomy_store.update_agent(campaign_id, agent_id, filtered)
        results[agent_id] = agent_cfg.model_dump()
    return results


# ── Event Bus & Triggers ─────────────────────────────────────────────────

@router.get("/events")
async def get_events(request: Request, campaign_id: str = "",
                     event_type: str = "", limit: int = 50):
    """Get recent events from the event bus."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if campaign_id:
        validate_id(campaign_id, "campaign_id")
    limit = min(limit, 200)

    results = event_bus.get_recent_events(limit=limit, campaign_id=campaign_id,
                                          event_type=event_type)
    if not results and db.is_persistent():
        try:
            results = await db.load_events(campaign_id=campaign_id,
                                            event_type=event_type, limit=limit)
        except Exception:
            pass
    return results


@router.get("/triggers")
async def list_triggers(request: Request):
    """List all trigger rules."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return [t.model_dump() for t in event_bus.get_triggers()]


@router.post("/triggers")
async def create_trigger(request: Request):
    """Create a new trigger rule."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    body = await request.json()
    if "event_type" in body and isinstance(body["event_type"], str):
        try:
            body["event_type"] = EventType(body["event_type"])
        except ValueError:
            raise HTTPException(400, f"Invalid event_type: {body['event_type']}")
    rule = TriggerRule(**body)
    rule_id = event_bus.add_trigger(rule)
    return {"id": rule_id, "status": "created"}


@router.put("/triggers/{rule_id}")
async def update_trigger(rule_id: str, request: Request):
    """Update an existing trigger rule."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(rule_id, "rule_id")

    body = await request.json()
    rule = event_bus.get_trigger(rule_id)
    if not rule:
        raise HTTPException(404, "Trigger not found")
    if "event_type" in body and isinstance(body["event_type"], str):
        try:
            body["event_type"] = EventType(body["event_type"])
        except ValueError:
            raise HTTPException(400, f"Invalid event_type: {body['event_type']}")
    event_bus.update_trigger(rule_id, body)
    return {"id": rule_id, "status": "updated"}


@router.delete("/triggers/{rule_id}")
async def delete_trigger(rule_id: str, request: Request):
    """Delete a trigger rule."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(rule_id, "rule_id")

    event_bus.remove_trigger(rule_id)
    return {"id": rule_id, "status": "deleted"}


@router.get("/triggers/event-types")
async def list_event_types(request: Request):
    """List all available event types for trigger configuration."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return [{"value": et.value, "label": et.name} for et in EventType]


# ── Business Profile ────────────────────────────────────────────────────

# In-memory business profile store scoped by user_id
_user_profiles: dict[str, dict] = {}

PROFILE_WRITABLE_FIELDS = {
    "name", "service", "icp", "geography", "goal", "entityType",
    "industry", "founderTitle", "brandContext", "websiteUrl",
    "pricingModel", "currentRevenue", "teamSize", "competitors",
    "biggestChallenge", "brandVoice", "businessModel", "startingFromScratch",
}


@router.post("/settings/business-profile")
async def update_business_profile(request: Request):
    """Update the user's business profile. Persists for future campaign runs."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    body = await request.json()
    filtered = {k: v for k, v in body.items() if k in PROFILE_WRITABLE_FIELDS}
    current = _user_profiles.get(user_id, {})
    current.update(filtered)
    _user_profiles[user_id] = current
    logger.info(f"User {user_id[:8]}... updated business profile ({len(filtered)} fields)")
    return {"updated": list(filtered.keys()), "count": len(filtered)}


@router.get("/settings/business-profile")
async def get_business_profile(request: Request):
    """Get the user's stored business profile."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return _user_profiles.get(user_id, {})


# ── Secrets (API Keys) ──────────────────────────────────────────────────

# Allowlisted secret key names that can be stored
_ALLOWED_SECRET_KEYS = {
    "SENDGRID_API_KEY", "HUBSPOT_API_KEY", "STRIPE_API_KEY",
    "SERPER_API_KEY", "TWITTER_BEARER_TOKEN", "APOLLO_API_KEY",
    "OPENAI_API_KEY", "VERCEL_TOKEN",
}

# In-memory secret store scoped by user_id (swap for vault in production)
_user_secrets: dict[str, dict[str, str]] = {}


@router.post("/settings/secrets")
async def store_secrets(request: Request):
    """Store API keys server-side. Never persisted in browser localStorage."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    body = await request.json()
    keys = body.get("keys", {})
    if not isinstance(keys, dict):
        raise HTTPException(400, "Expected {keys: {KEY_NAME: value}}")

    stored = []
    for key_name, value in keys.items():
        if key_name not in _ALLOWED_SECRET_KEYS:
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        _user_secrets.setdefault(user_id, {})[key_name] = value.strip()
        stored.append(key_name)

    logger.info(f"User {user_id[:8]}... stored {len(stored)} secrets")
    return {"stored": stored, "count": len(stored)}


@router.get("/settings/secrets")
async def list_secrets(request: Request):
    """List which secrets are configured (names only, never values)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    user_keys = _user_secrets.get(user_id, {})
    return {
        "configured": list(user_keys.keys()),
        "available": list(_ALLOWED_SECRET_KEYS),
    }


@router.delete("/settings/secrets/{key_name}")
async def delete_secret(key_name: str, request: Request):
    """Remove a stored secret."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    if key_name not in _ALLOWED_SECRET_KEYS:
        raise HTTPException(400, f"Unknown secret key: {key_name}")

    user_keys = _user_secrets.get(user_id, {})
    user_keys.pop(key_name, None)
    return {"deleted": key_name}
