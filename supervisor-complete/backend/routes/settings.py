"""Autonomy settings, agent settings, event bus triggers."""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Request

from autonomy import autonomy_store, AgentAutonomySettings
from eventbus import event_bus, EventType, TriggerRule
import db

logger = logging.getLogger("supervisor.api.settings")

router = APIRouter(tags=["Settings"])


# ── Autonomy Settings ────────────────────────────────────────────────────

@router.get("/settings/autonomy")
async def get_autonomy_settings(campaign_id: str = ""):
    """Get current autonomy settings (global or per-campaign)."""
    return autonomy_store.to_dict(campaign_id)


@router.put("/settings/autonomy")
async def update_autonomy_settings(request: Request, campaign_id: str = ""):
    """Update autonomy settings (global or per-campaign)."""
    body = await request.json()
    current = autonomy_store.get(campaign_id)

    for field in ["global_level", "spending_approval_threshold",
                  "outbound_approval_required", "content_approval_required",
                  "infrastructure_approval_required", "escalation_channel"]:
        if field in body:
            setattr(current, field, body[field])

    if campaign_id:
        autonomy_store.set(campaign_id, current)
    else:
        autonomy_store.set_global(current)

    return autonomy_store.to_dict(campaign_id)


@router.get("/settings/agents")
async def get_all_agent_settings(campaign_id: str = ""):
    """Get per-agent autonomy settings."""
    return autonomy_store.get_all_agent_settings(campaign_id)


@router.get("/settings/agents/{agent_id}")
async def get_agent_settings(agent_id: str, campaign_id: str = ""):
    """Get autonomy settings for a specific agent."""
    settings_obj = autonomy_store.get(campaign_id)
    agent_cfg = settings_obj.per_agent.get(agent_id)
    if agent_cfg:
        return agent_cfg.model_dump()
    return AgentAutonomySettings(agent_id=agent_id).model_dump()


@router.put("/settings/agents/{agent_id}")
async def update_agent_settings(agent_id: str, request: Request, campaign_id: str = ""):
    """Update autonomy settings for a specific agent."""
    body = await request.json()
    agent_cfg = autonomy_store.update_agent(campaign_id, agent_id, body)
    return agent_cfg.model_dump()


@router.post("/settings/agents/batch")
async def batch_update_agent_settings(request: Request, campaign_id: str = ""):
    """Batch update settings for multiple agents at once."""
    body = await request.json()
    results = {}
    for agent_id, updates in body.items():
        agent_cfg = autonomy_store.update_agent(campaign_id, agent_id, updates)
        results[agent_id] = agent_cfg.model_dump()
    return results


# ── Event Bus & Triggers ─────────────────────────────────────────────────

@router.get("/events")
async def get_events(campaign_id: str = "", event_type: str = "",
                     limit: int = 50):
    """Get recent events from the event bus."""
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
async def list_triggers():
    """List all trigger rules."""
    return [t.model_dump() for t in event_bus.get_triggers()]


@router.post("/triggers")
async def create_trigger(request: Request):
    """Create a new trigger rule."""
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
async def delete_trigger(rule_id: str):
    """Delete a trigger rule."""
    event_bus.remove_trigger(rule_id)
    return {"id": rule_id, "status": "deleted"}


@router.get("/triggers/event-types")
async def list_event_types():
    """List all available event types for trigger configuration."""
    return [{"value": et.value, "label": et.name} for et in EventType]
