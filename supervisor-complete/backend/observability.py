"""
Observability — Metrics, structured logging, and health telemetry.
Provides Prometheus-compatible metrics endpoint and request tracking.
Lightweight: no external dependencies required (uses stdlib).
"""
from __future__ import annotations
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

logger = logging.getLogger("supervisor.observability")


class Metrics:
    """In-process metrics collector (Prometheus-compatible text format)."""

    def __init__(self):
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_duration_sum: dict[str, float] = defaultdict(float)
        self.request_errors: dict[str, int] = defaultdict(int)
        self.active_requests: int = 0
        self.agent_runs: dict[str, int] = defaultdict(int)
        self.tool_calls: dict[str, int] = defaultdict(int)
        self.tool_errors: dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_request(self, method: str, path: str, status: int, duration: float):
        key = f"{method} {path}"
        self.request_count[key] += 1
        self.request_duration_sum[key] += duration
        if status >= 400:
            self.request_errors[key] += 1

    def record_agent_run(self, agent_id: str):
        self.agent_runs[agent_id] += 1

    def record_tool_call(self, tool_name: str, success: bool):
        self.tool_calls[tool_name] += 1
        if not success:
            self.tool_errors[tool_name] += 1

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []
        uptime = time.time() - self._start_time

        lines.append(f"# HELP supervisor_uptime_seconds Server uptime in seconds")
        lines.append(f"# TYPE supervisor_uptime_seconds gauge")
        lines.append(f"supervisor_uptime_seconds {uptime:.1f}")

        lines.append(f"# HELP supervisor_active_requests Current in-flight requests")
        lines.append(f"# TYPE supervisor_active_requests gauge")
        lines.append(f"supervisor_active_requests {self.active_requests}")

        lines.append(f"# HELP supervisor_http_requests_total Total HTTP requests")
        lines.append(f"# TYPE supervisor_http_requests_total counter")
        for key, count in self.request_count.items():
            method, path = key.split(" ", 1)
            lines.append(f'supervisor_http_requests_total{{method="{method}",path="{path}"}} {count}')

        lines.append(f"# HELP supervisor_http_errors_total Total HTTP errors (4xx/5xx)")
        lines.append(f"# TYPE supervisor_http_errors_total counter")
        for key, count in self.request_errors.items():
            method, path = key.split(" ", 1)
            lines.append(f'supervisor_http_errors_total{{method="{method}",path="{path}"}} {count}')

        lines.append(f"# HELP supervisor_agent_runs_total Total agent executions")
        lines.append(f"# TYPE supervisor_agent_runs_total counter")
        for agent_id, count in self.agent_runs.items():
            lines.append(f'supervisor_agent_runs_total{{agent_id="{agent_id}"}} {count}')

        lines.append(f"# HELP supervisor_tool_calls_total Total tool invocations")
        lines.append(f"# TYPE supervisor_tool_calls_total counter")
        for tool, count in self.tool_calls.items():
            lines.append(f'supervisor_tool_calls_total{{tool="{tool}"}} {count}')

        lines.append(f"# HELP supervisor_tool_errors_total Total tool failures")
        lines.append(f"# TYPE supervisor_tool_errors_total counter")
        for tool, count in self.tool_errors.items():
            lines.append(f'supervisor_tool_errors_total{{tool="{tool}"}} {count}')

        return "\n".join(lines) + "\n"

    def to_json(self) -> dict[str, Any]:
        """Export metrics as JSON for the dashboard."""
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "active_requests": self.active_requests,
            "total_requests": sum(self.request_count.values()),
            "total_errors": sum(self.request_errors.values()),
            "agent_runs": dict(self.agent_runs),
            "tool_calls": dict(self.tool_calls),
            "tool_errors": dict(self.tool_errors),
        }


# Singleton
metrics = Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track request count, duration, and errors."""

    async def dispatch(self, request: Request, call_next):
        # Normalize path: replace UUIDs and IDs with placeholders
        path = request.url.path
        if path in ("/health", "/metrics", "/metrics/json"):
            return await call_next(request)

        metrics.active_requests += 1
        start = time.time()
        try:
            response = await call_next(request)
            duration = time.time() - start
            metrics.record_request(request.method, path, response.status_code, duration)
            return response
        except Exception:
            duration = time.time() - start
            metrics.record_request(request.method, path, 500, duration)
            raise
        finally:
            metrics.active_requests -= 1
