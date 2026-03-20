"""
Semantic memory & RAG routes.

GET    /memory/{campaign_id}           — list memories
POST   /memory/{campaign_id}/search    — semantic search
POST   /memory/{campaign_id}/ingest    — manually ingest a document
DELETE /memory/{campaign_id}           — clear all memories
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any

from auth import get_user_id, validate_campaign_id
from memory import semantic_memory, rag_pipeline, MemoryType

router = APIRouter(tags=["Semantic Memory"])


# ── Request / Response models ───────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    memory_types: list[str] | None = None
    agent_id: str | None = None
    min_similarity: float = Field(default=0.1, ge=0.0, le=1.0)


class IngestRequest(BaseModel):
    text: str
    source: str = "manual"
    memory_type: str = "fact"
    metadata: dict[str, Any] | None = None


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/memory/{campaign_id}")
async def list_memories(
    campaign_id: str,
    request: Request,
    memory_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List memories for a campaign, optionally filtered by type."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)

    valid_types = {"episode", "lesson", "fact", "strategy"}
    mt = memory_type if memory_type in valid_types else None

    memories = semantic_memory.list_memories(
        campaign_id=campaign_id,
        memory_type=mt,  # type: ignore[arg-type]
        limit=min(limit, 200),
        offset=max(offset, 0),
    )
    return {
        "campaign_id": campaign_id,
        "count": len(memories),
        "total": semantic_memory.count(campaign_id),
        "memories": memories,
    }


@router.post("/memory/{campaign_id}/search")
async def search_memories(campaign_id: str, body: SearchRequest, request: Request):
    """Semantic search across campaign memories."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)

    valid_types = {"episode", "lesson", "fact", "strategy"}
    mt_filter = None
    if body.memory_types:
        mt_filter = [t for t in body.memory_types if t in valid_types]

    results = await semantic_memory.search(
        query=body.query,
        campaign_id=campaign_id,
        top_k=body.top_k,
        memory_types=mt_filter,  # type: ignore[arg-type]
        agent_id=body.agent_id,
        min_similarity=body.min_similarity,
    )
    return {
        "campaign_id": campaign_id,
        "query": body.query,
        "results": results,
        "count": len(results),
    }


@router.post("/memory/{campaign_id}/ingest")
async def ingest_document(campaign_id: str, body: IngestRequest, request: Request):
    """Manually ingest a document into campaign memory via RAG pipeline."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)

    if not body.text or not body.text.strip():
        raise HTTPException(400, "Text content is required")

    valid_types = {"episode", "lesson", "fact", "strategy"}
    mt = body.memory_type if body.memory_type in valid_types else "fact"

    chunk_count = await rag_pipeline.ingest(
        text=body.text,
        source=body.source,
        campaign_id=campaign_id,
        memory_type=mt,  # type: ignore[arg-type]
        metadata=body.metadata,
    )

    return {
        "campaign_id": campaign_id,
        "chunks_stored": chunk_count,
        "source": body.source,
        "memory_type": mt,
        "total_memories": semantic_memory.count(campaign_id),
    }


@router.delete("/memory/{campaign_id}")
async def clear_memories(campaign_id: str, request: Request):
    """Clear all memories for a campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)

    deleted = semantic_memory.clear(campaign_id)
    return {
        "campaign_id": campaign_id,
        "deleted": deleted,
    }
