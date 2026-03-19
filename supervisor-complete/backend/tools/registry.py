"""
Tool Registry — core ToolRegistry class and helpers.
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

import httpx

from models import ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger("supervisor.tools")

# Shared HTTP clients used by tool handlers across all domain modules.
_http = httpx.AsyncClient(timeout=30)
_http_long = httpx.AsyncClient(timeout=120)

# Default timeout (seconds) for tool execution
DEFAULT_TOOL_TIMEOUT = 60

# Per-category timeout overrides (seconds)
CATEGORY_TIMEOUTS: dict[str, float] = {
    "web": 30,
    "search": 20,
    "email": 30,
    "ai": 120,
    "deployment": 180,
    "manufacturing": 120,
    "nvidia": 120,
    "aws": 180,
}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}
        self._timeouts: dict[str, float] = {}  # per-tool timeout overrides

    def register(self, name: str, description: str, parameters: list[ToolParameter],
                 handler: Callable[..., Awaitable[str]], category: str = "general",
                 timeout: float | None = None):
        self._tools[name] = ToolDefinition(name=name, description=description, parameters=parameters, category=category)
        self._handlers[name] = handler
        if timeout is not None:
            self._timeouts[name] = timeout

    def _get_timeout(self, name: str) -> float:
        """Get timeout for a tool: explicit > category > default."""
        if name in self._timeouts:
            return self._timeouts[name]
        tool = self._tools.get(name)
        if tool and tool.category in CATEGORY_TIMEOUTS:
            return CATEGORY_TIMEOUTS[tool.category]
        return DEFAULT_TOOL_TIMEOUT

    def get_definitions(self, names: list[str] = None, categories: list[str] = None) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if names:
            tools = [t for t in tools if t.name in names]
        if categories:
            tools = [t for t in tools if t.category in categories]
        return tools

    async def execute(self, name: str, inputs: dict[str, Any], call_id: str = "") -> ToolResult:
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(tool_call_id=call_id, name=name, error=f"Unknown tool: {name}", success=False)
        timeout = self._get_timeout(name)
        try:
            output = await asyncio.wait_for(handler(**inputs), timeout=timeout)
            return ToolResult(tool_call_id=call_id, name=name, output=output, success=True)
        except asyncio.TimeoutError:
            logger.error(f"Tool {name} timed out after {timeout}s")
            return ToolResult(tool_call_id=call_id, name=name,
                              error=f"Tool timed out after {timeout}s", success=False)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return ToolResult(tool_call_id=call_id, name=name, error=str(e), success=False)

    @property
    def all_names(self) -> list[str]:
        return list(self._tools.keys())


def _to_json(obj) -> str:
    """Safely serialize an object that may be a dict or Pydantic model."""
    if hasattr(obj, 'model_dump'):
        return json.dumps(obj.model_dump(), default=str)
    return json.dumps(obj, default=str)
