"""Approval queue CRUD endpoints with tenant isolation and audit trail."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from models import ApprovalItem
from config import settings
from ws import ws_manager
from auth import get_user_id, require_auth, validate_id
from store import store
import db

logger = logging.getLogger("supervisor.api.approvals")

router = APIRouter(tags=["Approvals"])


# -- Request / response models ------------------------------------------------

class CreateApprovalRequest(BaseModel):
    campaign_id: str
    agent_id: str
    action_type: str
    content: dict = {}


class DecideApprovalRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    decided_by: str = "human"
    reason: str = ""


# -- Audit log (in-memory; persisted to DB when available) ---------------------

_audit_log: list[dict] = []


def _record_audit(item_id: str, action: str, actor: str, reason: str = "",
                  meta: Optional[dict] = None):
    entry = {
        "item_id": item_id,
        "action": action,
        "actor": actor,
        "reason": reason,
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _audit_log.append(entry)
    # Bound audit log to prevent unbounded memory growth
    if len(_audit_log) > 5000:
        del _audit_log[:1000]
    logger.info(f"Approval audit: {action} on {item_id} by {actor}")


# -- Endpoints ----------------------------------------------------------------

@router.get("/approvals")
async def list_approvals(request: Request, status: str = "pending",
                         offset: int = 0, limit: int = 50):
    """List approval queue items for the authenticated user (paginated)."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    all_items = store.list_approvals(user_id, status)
    total = len(all_items)
    page = all_items[offset:offset + limit]
    return {"items": [a.model_dump() for a in page], "count": len(page),
            "total": total, "offset": offset, "limit": limit}


@router.post("/approvals")
async def create_approval(req: CreateApprovalRequest, request: Request):
    """Create a new approval request -- notifies owner via Slack/Telegram/email."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    item = ApprovalItem(
        campaign_id=req.campaign_id,
        agent_id=req.agent_id,
        action_type=req.action_type,
        content=req.content,
    )
    store.put_approval(user_id, item)

    _record_audit(item.id, "created", user_id, meta={
        "campaign_id": req.campaign_id, "agent_id": req.agent_id,
        "action_type": req.action_type,
    })

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
async def decide_approval(item_id: str, req: DecideApprovalRequest,
                          request: Request):
    """Approve or reject an item in the approval queue."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    validate_id(item_id, "item_id")
    item = store.get_approval(user_id, item_id)
    if not item:
        raise HTTPException(404, "Approval item not found")

    item.status = req.decision
    item.decided_by = req.decided_by
    item.decided_at = datetime.now(timezone.utc)

    _record_audit(item.id, req.decision, user_id,
                  reason=req.reason,
                  meta={"decided_by": req.decided_by})

    await db.save_approval(item.model_dump())

    return {"id": item_id, "status": item.status, "decided_by": item.decided_by}


@router.get("/approvals/audit-log")
async def get_audit_log(request: Request, item_id: str = "",
                        limit: int = 100):
    """Get approval decision audit trail."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    entries = _audit_log
    if item_id:
        entries = [e for e in entries if e["item_id"] == item_id]
    return {"entries": entries[-limit:], "count": len(entries)}
