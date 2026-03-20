"""Compliance export endpoints: SOC2 reports, GDPR data inventory & deletion, audit trails."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth import get_user_id
from compliance import compliance_exporter

logger = logging.getLogger("omnios.routes.compliance")

router = APIRouter(tags=["Compliance"])


# ── Request models ──────────────────────────────────────────────────────────

class DeletionRequest(BaseModel):
    confirmation: str = ""  # Must be "DELETE" to proceed


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/compliance/audit-trail")
async def get_audit_trail(request: Request, start: str = "", end: str = ""):
    """Export audit trail for a date range.

    Query params:
      - start: YYYY-MM-DD (defaults to 30 days ago)
      - end:   YYYY-MM-DD (defaults to today)
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    from datetime import datetime, timedelta, timezone
    if not start:
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    report = await compliance_exporter.export_audit_trail(start, end)
    return report


@router.get("/compliance/data-inventory")
async def get_data_inventory(request: Request):
    """GDPR data inventory: what data the system holds for the current user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    inventory = await compliance_exporter.export_data_inventory(user_id)
    return inventory


@router.post("/compliance/deletion-request")
async def request_deletion(req: DeletionRequest, request: Request):
    """GDPR right-to-delete: remove all user data.

    Requires confirmation field set to "DELETE" to proceed.
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    if req.confirmation != "DELETE":
        raise HTTPException(
            400,
            "Deletion requires confirmation. Set confirmation to 'DELETE' to proceed."
        )

    result = await compliance_exporter.handle_deletion_request(user_id)
    return result


@router.get("/compliance/soc2-report")
async def get_soc2_report(request: Request, period: str = ""):
    """Generate SOC2 summary report.

    Query param:
      - period: "2026-Q1", "2026-03", or "2026" (defaults to current month)
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    if not period:
        from datetime import datetime, timezone
        period = datetime.now(timezone.utc).strftime("%Y-%m")

    report = await compliance_exporter.generate_soc2_report(period)
    return report


@router.get("/compliance/access-log")
async def get_access_log(request: Request, start: str = "", end: str = ""):
    """Export access history for the current user.

    Query params:
      - start: YYYY-MM-DD (defaults to 30 days ago)
      - end:   YYYY-MM-DD (defaults to today)
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    from datetime import datetime, timedelta, timezone
    if not start:
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    report = await compliance_exporter.export_access_log(user_id, start, end)
    return report
