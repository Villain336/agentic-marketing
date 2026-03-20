"""
Routes for the step-level agent tracing system.
Provides endpoints to list, inspect, and manage agent execution traces.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id
from tracing import trace_store

router = APIRouter(tags=["Tracing"])


@router.get("/traces")
async def list_traces(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    agent_id: str = "",
    campaign_id: str = "",
):
    """List recent traces with optional filtering and pagination."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    # Clamp limit to a reasonable range
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    traces = trace_store.list_recent(
        limit=limit, offset=offset,
        agent_id=agent_id or None,
        campaign_id=campaign_id or None,
    )
    total = trace_store.count(
        agent_id=agent_id or None,
        campaign_id=campaign_id or None,
    )
    active = trace_store.active_traces()

    return {
        "traces": [t.to_summary() for t in traces],
        "total": total,
        "limit": limit,
        "offset": offset,
        "active_count": len(active),
    }


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    """Get a full trace with all spans."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    trace = trace_store.get(trace_id)
    if not trace:
        raise HTTPException(404, "Trace not found")

    return trace.to_dict()


@router.get("/traces/{trace_id}/timeline")
async def get_trace_timeline(trace_id: str, request: Request):
    """Get spans as a timeline sorted by start time."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    trace = trace_store.get(trace_id)
    if not trace:
        raise HTTPException(404, "Trace not found")

    return {
        "trace_id": trace.trace_id,
        "agent_id": trace.agent_id,
        "campaign_id": trace.campaign_id,
        "duration_ms": trace.duration_ms,
        "timeline": trace.to_timeline(),
    }


@router.delete("/traces")
async def clear_traces(
    request: Request,
    older_than_hours: float = 0,
):
    """
    Clear old traces. If older_than_hours is provided, only traces older
    than that threshold are removed. Otherwise all completed traces are cleared.
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    before_ts = None
    if older_than_hours > 0:
        before_ts = time.time() - (older_than_hours * 3600)

    count_before = trace_store.count()
    trace_store.clear(before_ts=before_ts)
    count_after = trace_store.count()

    return {
        "cleared": count_before - count_after,
        "remaining": count_after,
    }
