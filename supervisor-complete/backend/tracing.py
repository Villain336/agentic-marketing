"""
Omni OS Backend — Step-Level Agent Tracing System
Captures every step of agent execution: LLM calls, tool calls, decisions,
parent-child relationships for multi-agent workflows.
Lightweight: no external dependencies — uses stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("omnios.tracing")


# ═══════════════════════════════════════════════════════════════════════════════
# SPAN TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class SpanKind(str, Enum):
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    QUALITY_GATE = "quality_gate"
    MEMORY_EXTRACTION = "memory_extraction"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


# ═══════════════════════════════════════════════════════════════════════════════
# SPAN — A single timed operation within a trace
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Span:
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    kind: SpanKind = SpanKind.AGENT
    name: str = ""
    status: SpanStatus = SpanStatus.OK

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None

    # LLM-specific
    model: Optional[str] = None
    provider: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_hash: Optional[str] = None

    # Tool-specific
    tool_name: Optional[str] = None
    tool_input_summary: Optional[str] = None
    tool_output_summary: Optional[str] = None
    tool_success: Optional[bool] = None

    # Decision-specific
    decision_reason: Optional[str] = None
    decision_action: Optional[str] = None

    # General metadata
    step_number: int = 0
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    def finish(self, status: SpanStatus = None, error: str = None):
        """Finalize span timing."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if status:
            self.status = status
        if error:
            self.error = error
            if not status:
                self.status = SpanStatus.ERROR

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["start_time_iso"] = datetime.fromtimestamp(self.start_time).isoformat()
        if self.end_time:
            d["end_time_iso"] = datetime.fromtimestamp(self.end_time).isoformat()
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# TRACE — A complete agent execution with all its spans
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_trace_id: Optional[str] = None
    agent_id: str = ""
    campaign_id: str = ""
    user_id: str = ""

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None

    # Summary
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_iterations: int = 0
    estimated_cost_usd: float = 0.0
    final_status: SpanStatus = SpanStatus.OK

    # Model info
    model: Optional[str] = None
    provider: Optional[str] = None

    # Quality
    quality_passed: Optional[bool] = None
    quality_issues: list[str] = field(default_factory=list)

    # Spans
    spans: list[Span] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # ── Span creation helpers ─────────────────────────────────────────────

    def start_llm_span(self, step: int, model: str = None,
                       prompt_hash: str = None,
                       parent_span_id: str = None) -> Span:
        """Begin tracking an LLM call."""
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.LLM_CALL,
            name=f"llm_call_step_{step}",
            model=model,
            prompt_hash=prompt_hash,
            step_number=step,
        )
        self.spans.append(span)
        return span

    def finish_llm_span(self, span: Span, provider: str = "",
                        model: str = "", input_tokens: int = 0,
                        output_tokens: int = 0, error: str = None):
        """Finalize an LLM call span."""
        span.provider = provider or span.provider
        span.model = model or span.model
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        span.finish(error=error)
        self.total_llm_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        if provider:
            self.provider = provider
        if model:
            self.model = model

    def start_tool_span(self, step: int, tool_name: str,
                        tool_input: dict, parent_span_id: str = None) -> Span:
        """Begin tracking a tool call."""
        # Summarize input — truncate large values
        input_summary = _summarize_dict(tool_input, max_len=200)
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.TOOL_CALL,
            name=f"tool_{tool_name}",
            tool_name=tool_name,
            tool_input_summary=input_summary,
            step_number=step,
        )
        self.spans.append(span)
        return span

    def finish_tool_span(self, span: Span, success: bool,
                         output: str = "", error: str = None):
        """Finalize a tool call span."""
        span.tool_success = success
        span.tool_output_summary = (output[:200] + "...") if len(output) > 200 else output
        status = SpanStatus.OK if success else SpanStatus.ERROR
        span.finish(status=status, error=error)
        self.total_tool_calls += 1

    def record_decision(self, step: int, action: str, reason: str,
                        parent_span_id: str = None) -> Span:
        """Record why the agent chose a particular action."""
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.DECISION,
            name=f"decision_step_{step}",
            decision_action=action,
            decision_reason=reason,
            step_number=step,
        )
        span.finish()
        self.spans.append(span)
        return span

    def record_quality_gate(self, passed: bool, issues: list[str]) -> Span:
        """Record quality gate result."""
        span = Span(
            trace_id=self.trace_id,
            kind=SpanKind.QUALITY_GATE,
            name="quality_gate",
            metadata={"passed": passed, "issues": issues},
        )
        span.finish(status=SpanStatus.OK if passed else SpanStatus.ERROR)
        self.spans.append(span)
        self.quality_passed = passed
        self.quality_issues = issues
        return span

    def finalize(self, status: SpanStatus = None, estimated_cost: float = 0.0):
        """Finalize the entire trace."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if status:
            self.final_status = status
        self.estimated_cost_usd = estimated_cost

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "agent_id": self.agent_id,
            "campaign_id": self.campaign_id,
            "user_id": self.user_id,
            "start_time": self.start_time,
            "start_time_iso": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": self.end_time,
            "end_time_iso": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_iterations": self.total_iterations,
            "estimated_cost_usd": self.estimated_cost_usd,
            "final_status": self.final_status.value,
            "model": self.model,
            "provider": self.provider,
            "quality_passed": self.quality_passed,
            "quality_issues": self.quality_issues,
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }

    def to_summary(self) -> dict:
        """Lightweight summary without full span details."""
        return {
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "agent_id": self.agent_id,
            "campaign_id": self.campaign_id,
            "start_time_iso": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_ms": self.duration_ms,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_iterations": self.total_iterations,
            "estimated_cost_usd": self.estimated_cost_usd,
            "final_status": self.final_status.value,
            "model": self.model,
            "provider": self.provider,
            "quality_passed": self.quality_passed,
            "span_count": len(self.spans),
        }

    def to_timeline(self) -> list[dict]:
        """Return spans sorted by start time for timeline rendering."""
        sorted_spans = sorted(self.spans, key=lambda s: s.start_time)
        timeline = []
        for s in sorted_spans:
            entry = {
                "span_id": s.span_id,
                "kind": s.kind.value,
                "name": s.name,
                "start_time_iso": datetime.fromtimestamp(s.start_time).isoformat(),
                "duration_ms": s.duration_ms,
                "status": s.status.value,
                "step_number": s.step_number,
            }
            # Add kind-specific fields
            if s.kind == SpanKind.LLM_CALL:
                entry["model"] = s.model
                entry["input_tokens"] = s.input_tokens
                entry["output_tokens"] = s.output_tokens
            elif s.kind == SpanKind.TOOL_CALL:
                entry["tool_name"] = s.tool_name
                entry["tool_success"] = s.tool_success
                entry["tool_input_summary"] = s.tool_input_summary
            elif s.kind == SpanKind.DECISION:
                entry["decision_action"] = s.decision_action
                entry["decision_reason"] = s.decision_reason
            if s.error:
                entry["error"] = s.error
            timeline.append(entry)
        return timeline


# ═══════════════════════════════════════════════════════════════════════════════
# SPAN CONTEXT — Context manager for timing operations
# ═══════════════════════════════════════════════════════════════════════════════

class SpanContext:
    """Context manager for conveniently timing a span within a trace."""

    def __init__(self, trace: Trace, kind: SpanKind, name: str,
                 step: int = 0, parent_span_id: str = None, **metadata):
        self.trace = trace
        self.span = Span(
            trace_id=trace.trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            name=name,
            step_number=step,
            metadata=metadata,
        )
        self.trace.spans.append(self.span)

    def __enter__(self) -> Span:
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.span.finish(
                status=SpanStatus.ERROR,
                error=str(exc_val) if exc_val else "Unknown error",
            )
        else:
            self.span.finish()
        return False  # don't suppress exceptions


# ═══════════════════════════════════════════════════════════════════════════════
# TRACE STORE — Singleton in-memory store with DB persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TraceStore:
    """
    Thread-safe, bounded in-memory trace store.
    Persists completed traces to database when available.
    """

    MAX_TRACES = 500  # max in-memory traces to retain

    def __init__(self):
        self._traces: deque[Trace] = deque(maxlen=self.MAX_TRACES)
        self._index: dict[str, Trace] = {}  # trace_id -> Trace
        self._lock = Lock()
        # Active traces (not yet finalized)
        self._active: dict[str, Trace] = {}

    def start_trace(self, agent_id: str, campaign_id: str = "",
                    user_id: str = "", parent_trace_id: str = None) -> Trace:
        """Create and register a new trace."""
        trace = Trace(
            agent_id=agent_id,
            campaign_id=campaign_id,
            user_id=user_id,
            parent_trace_id=parent_trace_id,
        )
        with self._lock:
            self._active[trace.trace_id] = trace
        logger.debug(f"Trace started: {trace.trace_id} for agent={agent_id}")
        return trace

    def finish_trace(self, trace: Trace):
        """Finalize a trace, move from active to stored."""
        with self._lock:
            self._active.pop(trace.trace_id, None)
            self._traces.append(trace)
            # Evict oldest from index if at capacity
            if len(self._index) >= self.MAX_TRACES:
                oldest_id = self._traces[0].trace_id if self._traces else None
                if oldest_id and oldest_id in self._index:
                    del self._index[oldest_id]
            self._index[trace.trace_id] = trace
        logger.debug(
            f"Trace finished: {trace.trace_id} agent={trace.agent_id} "
            f"duration={trace.duration_ms}ms spans={len(trace.spans)}"
        )
        # Fire-and-forget DB persistence
        self._persist_async(trace)

    def get(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID (completed or active)."""
        with self._lock:
            return self._index.get(trace_id) or self._active.get(trace_id)

    def list_recent(self, limit: int = 50, offset: int = 0,
                    agent_id: str = None, campaign_id: str = None) -> list[Trace]:
        """List recent traces with optional filtering."""
        with self._lock:
            all_traces = list(self._traces)
        # Newest first
        all_traces.reverse()
        # Filter
        if agent_id:
            all_traces = [t for t in all_traces if t.agent_id == agent_id]
        if campaign_id:
            all_traces = [t for t in all_traces if t.campaign_id == campaign_id]
        return all_traces[offset:offset + limit]

    def count(self, agent_id: str = None, campaign_id: str = None) -> int:
        """Count traces, optionally filtered."""
        with self._lock:
            all_traces = list(self._traces)
        if agent_id:
            all_traces = [t for t in all_traces if t.agent_id == agent_id]
        if campaign_id:
            all_traces = [t for t in all_traces if t.campaign_id == campaign_id]
        return len(all_traces)

    def active_traces(self) -> list[Trace]:
        """Return currently running traces."""
        with self._lock:
            return list(self._active.values())

    def clear(self, before_ts: float = None):
        """Clear traces, optionally only those older than a timestamp."""
        with self._lock:
            if before_ts is None:
                self._traces.clear()
                self._index.clear()
            else:
                kept = deque(maxlen=self.MAX_TRACES)
                for t in self._traces:
                    if t.start_time >= before_ts:
                        kept.append(t)
                    else:
                        self._index.pop(t.trace_id, None)
                self._traces = kept

    def _persist_async(self, trace: Trace):
        """Persist trace to DB in background (best-effort)."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._persist_to_db(trace))
            else:
                # No running loop — skip DB persistence
                pass
        except RuntimeError:
            pass

    async def _persist_to_db(self, trace: Trace):
        """Persist a completed trace to the database."""
        try:
            import db
            if not db.is_persistent():
                return
            client = db._get_client()
            if not client:
                return
            data = {
                "id": trace.trace_id,
                "agent_id": trace.agent_id,
                "campaign_id": trace.campaign_id or None,
                "user_id": trace.user_id or None,
                "parent_trace_id": trace.parent_trace_id,
                "start_time": datetime.fromtimestamp(trace.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(trace.end_time).isoformat() if trace.end_time else None,
                "duration_ms": trace.duration_ms,
                "total_llm_calls": trace.total_llm_calls,
                "total_tool_calls": trace.total_tool_calls,
                "total_input_tokens": trace.total_input_tokens,
                "total_output_tokens": trace.total_output_tokens,
                "total_iterations": trace.total_iterations,
                "estimated_cost_usd": trace.estimated_cost_usd,
                "final_status": trace.final_status.value,
                "model": trace.model,
                "provider": trace.provider,
                "quality_passed": trace.quality_passed,
                "quality_issues": trace.quality_issues,
                "spans": json.dumps([s.to_dict() for s in trace.spans]),
                "metadata": json.dumps(trace.metadata),
            }
            client.table("agent_traces").upsert(data).execute()
            logger.debug(f"Trace {trace.trace_id} persisted to DB")
        except Exception as e:
            logger.debug(f"Trace DB persistence skipped: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _summarize_dict(d: dict, max_len: int = 200) -> str:
    """Create a short summary string from a dict."""
    try:
        s = json.dumps(d, default=str)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    except Exception:
        return str(d)[:max_len]


def compute_prompt_hash(messages: list[dict], system: str = "") -> str:
    """Hash the prompt for deduplication / caching analysis."""
    hasher = hashlib.sha256()
    hasher.update(system.encode("utf-8", errors="replace"))
    for m in messages:
        content = str(m.get("content", ""))
        hasher.update(content.encode("utf-8", errors="replace"))
    return hasher.hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

trace_store = TraceStore()
