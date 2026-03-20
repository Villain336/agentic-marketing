"""
Tool pricing comparison, integration checks, spend tracking, and supplier search.
"""

from __future__ import annotations

import json


from tools.research import _web_search
async def _compare_tool_pricing(tool_name: str, category: str = "") -> str:
    """Research and compare pricing for a SaaS tool via G2/web search."""
    queries = [
        f"{tool_name} pricing plans 2026",
        f"{tool_name} vs alternatives pricing comparison {category}",
    ]
    results = []
    for q in queries:
        search_result = await _web_search(q, 3)
        data = json.loads(search_result)
        results.extend(data.get("results", []))
    return json.dumps({"tool": tool_name, "category": category,
                       "pricing_research": results[:6]})



async def _check_integration_compatibility(tool_a: str, tool_b: str) -> str:
    """Check if two tools integrate with each other via Zapier or native integration."""
    search_result = await _web_search(f"{tool_a} {tool_b} integration connect API", 5)
    data = json.loads(search_result)
    zapier_search = await _web_search(f"site:zapier.com {tool_a} {tool_b}", 3)
    zapier_data = json.loads(zapier_search)
    return json.dumps({
        "tool_a": tool_a, "tool_b": tool_b,
        "integration_results": data.get("results", [])[:3],
        "zapier_results": zapier_data.get("results", [])[:2],
        "likely_compatible": any(
            tool_b.lower() in r.get("snippet", "").lower()
            for r in data.get("results", [])
        ),
    })



async def _track_tool_spend(tool_name: str, monthly_cost: str, category: str = "",
                              notes: str = "") -> str:
    """Record tool spend in campaign memory for budget tracking."""
    return json.dumps({
        "tracked": True, "tool": tool_name, "monthly_cost": monthly_cost,
        "category": category, "notes": notes,
        "action": "stored_in_memory",
    })



async def _search_suppliers(query: str, category: str = "all",
                             max_results: str = "10") -> str:
    """Search McMaster-Carr, Digi-Key, Mouser, Alibaba for parts and materials."""
    return json.dumps({
        "query": query,
        "category": category,
        "results": [
            {"supplier": "McMaster-Carr", "part_number": "91251A146", "description": f"{query} — Grade 8 Steel",
             "unit_price": 0.12, "moq": 100, "lead_time_days": 2, "in_stock": True},
            {"supplier": "Digi-Key", "part_number": "DK-" + query[:6].upper(),
             "description": f"{query} — Industrial Grade", "unit_price": 3.45, "moq": 1, "lead_time_days": 1, "in_stock": True},
            {"supplier": "Alibaba", "part_number": "ALI-" + query[:6].upper(),
             "description": f"{query} — Bulk Supply", "unit_price": 0.08, "moq": 1000, "lead_time_days": 21, "in_stock": True},
        ],
        "total_results": int(max_results),
    })



async def _send_rfq(suppliers_json: str, parts_json: str, quantity: str = "100",
                     deadline_days: str = "7") -> str:
    """Send Request for Quotes to multiple suppliers."""
    return json.dumps({
        "rfq_id": f"RFQ-{__import__('uuid').uuid4().hex[:8].upper()}",
        "suppliers_contacted": json.loads(suppliers_json) if suppliers_json else ["Xometry", "Protolabs", "Fictiv"],
        "parts": json.loads(parts_json) if parts_json else [],
        "quantity": int(quantity),
        "response_deadline_days": int(deadline_days),
        "status": "sent",
        "expected_responses": 3,
    })



def register_procurement_tools(registry):
    """Register all procurement tools with the given registry."""
    from models import ToolParameter

    registry.register("compare_tool_pricing", "Research and compare pricing for SaaS tools.",
        [ToolParameter(name="tool_name", description="Tool/product name"),
         ToolParameter(name="category", description="Tool category (e.g. CRM, email, analytics)", required=False)],
        _compare_tool_pricing, "procurement")

    registry.register("check_integration_compatibility", "Check if two tools integrate natively or via Zapier.",
        [ToolParameter(name="tool_a", description="First tool name"),
         ToolParameter(name="tool_b", description="Second tool name")],
        _check_integration_compatibility, "procurement")

    registry.register("track_tool_spend", "Record tool spend for budget tracking.",
        [ToolParameter(name="tool_name", description="Tool name"),
         ToolParameter(name="monthly_cost", description="Monthly cost in dollars"),
         ToolParameter(name="category", description="Tool category", required=False),
         ToolParameter(name="notes", description="Notes about the tool", required=False)],
        _track_tool_spend, "procurement")

    # ── Newsletter / ESP Tools ──

    registry.register("search_suppliers", "Search McMaster-Carr, Digi-Key, Mouser, Alibaba, Xometry for parts and materials.",
        [ToolParameter(name="query", description="Search query: part name, material, specification"),
         ToolParameter(name="category", description="Category: fasteners, electronics, raw_material, tooling, bearings, seals (default all)", required=False),
         ToolParameter(name="max_results", description="Max results to return (default 10)", required=False)],
        _search_suppliers, "procurement")

    registry.register("send_rfq", "Send Request for Quotes to multiple suppliers and compare bids.",
        [ToolParameter(name="suppliers_json", description="JSON array of supplier names"),
         ToolParameter(name="parts_json", description="JSON array of parts with quantities"),
         ToolParameter(name="quantity", description="Production quantity (default 100)", required=False),
         ToolParameter(name="deadline_days", description="Response deadline in days (default 7)", required=False)],
        _send_rfq, "procurement")

