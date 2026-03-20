"""
Campaign memory store and read.
"""

from __future__ import annotations

import json


async def _store_data(key: str, value: str, namespace: str = "campaign") -> str:
    return json.dumps({"stored": True, "key": f"{namespace}:{key}", "size": len(value)})



async def _read_data(key: str, namespace: str = "campaign") -> str:
    return json.dumps({"key": f"{namespace}:{key}", "note": "Connect Supabase for persistence."})



def register_memory_tools(registry):
    """Register all memory tools with the given registry."""
    from models import ToolParameter

    registry.register("store_data", "Store data in campaign memory for other agents to reference.",
        [ToolParameter(name="key", description="Key name (e.g. 'qualified_prospects')"),
         ToolParameter(name="value", description="Data to store"),
         ToolParameter(name="namespace", description="Namespace", required=False)],
        _store_data, "memory")

    registry.register("read_data", "Read previously stored data from campaign memory.",
        [ToolParameter(name="key", description="Key to read"),
         ToolParameter(name="namespace", description="Namespace", required=False)],
        _read_data, "memory")

    # ── Email Tools ──

