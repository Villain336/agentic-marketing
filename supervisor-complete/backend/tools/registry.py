"""
Tool Registry — core ToolRegistry class and helpers.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Callable, Awaitable

import httpx

from models import ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger("supervisor.tools")

# Shared HTTP clients used by tool handlers across all domain modules.
_http = httpx.AsyncClient(timeout=30)
_http_long = httpx.AsyncClient(timeout=120)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}

    def register(self, name: str, description: str, parameters: list[ToolParameter],
                 handler: Callable[..., Awaitable[str]], category: str = "general"):
        self._tools[name] = ToolDefinition(name=name, description=description, parameters=parameters, category=category)
        self._handlers[name] = handler

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
        try:
            output = await handler(**inputs)
            return ToolResult(tool_call_id=call_id, name=name, output=output, success=True)
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
