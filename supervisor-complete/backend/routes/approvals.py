"""Approval queue CRUD endpoints."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from models import ApprovalItem
from config import settings
from ws import ws_manager
from store import approval_queue
import db

logger = logging.getLogger("supervisor.api.approvals")

router = APIRouter(tags=["Approvals"])


@router.get("/approvals")
async def list_approvals(status: str = "pending"):
    """List approval queue items filtered by status."""
    items = [a.model_dump() for a in approval_queue.values() if a.status == status]
    return {"items": items, "count": len(items)}


@router.post("/approvals")
async def create_approval(request: Request):
    """Create a new approval request — notifies owner via Slack/Telegram/email."""
    body = await request.json()
    item = ApprovalItem(
        campaign_id=body.get("campaign_id", ""),
        agent_id=body.get("agent_id", ""),
        action_type=body.get("action_type", ""),
        content=body.get("content", {}),
    )
    approval_queue[item.id] = item

    asyncio.create_task(ws_manager.send_approval_needed(
        item.campaign_id, {"id": item.id, "agent_id": item.agent_id,
                           "action_type": item.action_type}))

    asyncio.create_task(_notify_approval_needed(item))

    await db.save_approval(item.model_dump())

    return {"id": item.id, "status": "pending"}


async def _notify_approval_needed(item: ApprovalItem):
    """Send approval notification via Slack, Telegram, or email."""
    from tools import registry

    msg = (f"Approval needed: {item.action_type}\n"
           f"Agent: {item.agent_id}\n"
           f"Campaign: {item.campaign_id}\n"
           f"ID: {item.id}")

    if settings.slack_bot_token:
        try:
            await registry.execute("send_slack_message",
                {"channel": "#approvals", "message": msg}, "approval")
        except Exception:
            pass

    if settings.telegram_bot_token and settings.telegram_owner_chat_id:
        try:
            await registry.execute("send_telegram_message",
                {"message": msg}, "approval")
        except Exception:
            pass

    if settings.owner_email and settings.sendgrid_api_key:
        try:
            await registry.execute("send_email",
                {"to": settings.owner_email, "subject": f"Approval Needed: {item.action_type}",
                 "body": msg}, "approval")
        except Exception:
            pass


@router.post("/approvals/{item_id}/decide")
async def decide_approval(item_id: str, request: Request):
    """Approve or reject an item in the approval queue."""
    item = approval_queue.get(item_id)
    if not item:
        raise HTTPException(404, "Approval item not found")

    body = await request.json()
    decision = body.get("decision", "")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "Decision must be 'approved' or 'rejected'")

    item.status = decision
    item.decided_by = body.get("decided_by", "human")
    item.decided_at = datetime.utcnow()

    return {"id": item_id, "status": item.status, "decided_by": item.decided_by}
