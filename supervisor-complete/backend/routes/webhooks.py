"""Webhook receiver and sensing trigger execution."""
from __future__ import annotations
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from models import Campaign, PerformanceEvent, Tier
from engine import engine
from agents import get_agent
from sensing import sensing
from ws import ws_manager
from webhook_auth import verify_webhook
from store import store
import db

logger = logging.getLogger("supervisor.api.webhooks")

router = APIRouter(tags=["Webhooks"])


@router.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    """Universal webhook receiver for external services."""
    raw_body = await request.body()
    headers = dict(request.headers)
    if not verify_webhook(source, raw_body, headers):
        logger.warning(f"Webhook signature verification failed for {source}")
        raise HTTPException(401, "Invalid webhook signature")

    body = await request.json()
    campaign_id = body.get("campaign_id", "")

    if not campaign_id:
        campaign_id = request.headers.get("X-Campaign-ID", "")

    # Webhooks use cross-tenant lookup (they come from external services)
    campaign = store.get_campaign_any_tenant(campaign_id) if campaign_id else None
    if not campaign:
        logger.warning(f"Webhook from {source} but no matching campaign")
        return {"received": True, "processed": False, "reason": "no matching campaign"}

    event = PerformanceEvent(campaign_id=campaign_id, source=source,
                              event_type=body.get("event", body.get("type", "")),
                              data=body)

    await db.save_performance_event({
        "id": event.id, "campaign_id": campaign_id, "source": source,
        "event_type": event.event_type, "data": body,
    })

    trigger = await sensing.process_event(campaign, event)

    result = {"received": True, "processed": True, "source": source}
    if trigger:
        result["trigger"] = trigger
        logger.info(f"Webhook trigger: {trigger}")
        asyncio.create_task(ws_manager.send_trigger_fired(campaign_id, trigger))
        if trigger.get("trigger") == "rerun_agent":
            agent_id = trigger.get("agent_id")
            reason = trigger.get("reason", "threshold breach")
            asyncio.create_task(
                _execute_sensing_trigger(campaign, agent_id, reason)
            )
            result["action"] = f"Scheduled re-run of {agent_id}"

    return result


async def _execute_sensing_trigger(campaign: Campaign, agent_id: str, reason: str):
    """Background task: re-run an agent after a sensing trigger fires."""
    agent = get_agent(agent_id)
    if not agent:
        logger.error(f"Sensing trigger: agent {agent_id} not found")
        return

    logger.info(f"Sensing trigger executing: re-running {agent_id} -- {reason}")

    try:
        async for event in engine.run(
            agent=agent, memory=campaign.memory,
            campaign_id=campaign.id, tier=Tier.STANDARD,
            campaign=campaign, trigger_reason=reason,
        ):
            if event.memory_update:
                for k, v in event.memory_update.items():
                    if hasattr(campaign.memory, k):
                        setattr(campaign.memory, k, v)
        logger.info(f"Sensing trigger complete: {agent_id} re-run finished")
    except Exception as e:
        logger.error(f"Sensing trigger failed for {agent_id}: {e}", exc_info=True)
