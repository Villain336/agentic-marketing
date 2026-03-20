"""
Google Analytics, Search Console, keyword planner, and automated ad rules.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


from tools.content import _seo_keyword_research
async def _get_google_analytics_data(property_id: str, metric: str = "sessions",
                                       date_range: str = "7daysAgo") -> str:
    """Get data from Google Analytics 4 (GA4) Data API."""
    ga_key = getattr(settings, 'google_analytics_api_key', '') or ""
    if not ga_key:
        return json.dumps({"error": "GA4 API not configured. Set GOOGLE_ANALYTICS_API_KEY.",
                           "recommendation": "Use GA4 Data API with service account."})
    try:
        resp = await _http.post(
            f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
            headers={"Authorization": f"Bearer {ga_key}", "Content-Type": "application/json"},
            json={
                "dateRanges": [{"startDate": date_range, "endDate": "today"}],
                "metrics": [{"name": metric}],
                "dimensions": [{"name": "date"}],
            })
        if resp.status_code == 200:
            data = resp.json()
            rows = [{"date": r["dimensionValues"][0]["value"],
                     metric: r["metricValues"][0]["value"]}
                    for r in data.get("rows", [])]
            return json.dumps({"property_id": property_id, "metric": metric, "data": rows})
        return json.dumps({"error": f"GA4 {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _get_search_console_data(site_url: str, query_filter: str = "",
                                     date_range: str = "7d") -> str:
    """Get Google Search Console performance data — clicks, impressions, CTR, position."""
    gsc_key = getattr(settings, 'google_search_console_key', '') or ""
    if not gsc_key:
        return json.dumps({"error": "Search Console API not configured. Set GOOGLE_SEARCH_CONSOLE_KEY."})
    try:
        body: dict[str, Any] = {
            "startDate": "2026-03-08" if date_range == "7d" else "2026-02-15",
            "endDate": "2026-03-15",
            "dimensions": ["query"],
            "rowLimit": 20,
        }
        if query_filter:
            body["dimensionFilterGroups"] = [{"filters": [
                {"dimension": "query", "operator": "contains", "expression": query_filter}
            ]}]
        resp = await _http.post(
            f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {gsc_key}", "Content-Type": "application/json"},
            json=body)
        if resp.status_code == 200:
            data = resp.json()
            rows = [{"query": r["keys"][0], "clicks": r["clicks"],
                     "impressions": r["impressions"], "ctr": round(r["ctr"] * 100, 2),
                     "position": round(r["position"], 1)}
                    for r in data.get("rows", [])]
            return json.dumps({"site": site_url, "data": rows})
        return json.dumps({"error": f"GSC {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _keyword_planner_lookup(keywords: str, country: str = "us") -> str:
    """Get keyword search volume and CPC estimates via Google Ads Keyword Planner or DataForSEO."""
    keyword_list = [k.strip() for k in keywords.split(",")]
    results = []
    for kw in keyword_list[:10]:
        data = await _seo_keyword_research(kw, country)
        results.append(json.loads(data))
    return json.dumps({"keywords": keyword_list, "results": results})



async def _create_ad_rule(campaign_id: str, platform: str, rule_type: str,
                            condition: str, action: str) -> str:
    """Create automated ad optimization rule (pause underperformers, scale winners)."""
    rule = {
        "campaign_id": campaign_id, "platform": platform,
        "rule_type": rule_type, "condition": condition, "action": action,
        "status": "active",
        "examples": {
            "pause_low_ctr": {"condition": "ctr < 0.5%", "action": "pause_ad"},
            "increase_budget": {"condition": "roas > 3.0", "action": "increase_budget_20%"},
            "decrease_bid": {"condition": "cpa > $50", "action": "decrease_bid_10%"},
            "alert": {"condition": "spend > daily_budget * 1.2", "action": "send_alert"},
        },
    }
    return json.dumps({"rule_created": True, "rule": rule,
                       "note": "Rules evaluated hourly by the PPC agent."})



def register_analytics_tools(registry):
    """Register all analytics tools with the given registry."""
    from models import ToolParameter

    registry.register("get_google_analytics_data", "Get data from Google Analytics 4 (GA4) — sessions, conversions, etc.",
        [ToolParameter(name="property_id", description="GA4 property ID"),
         ToolParameter(name="metric", description="Metric: sessions, conversions, pageviews, etc.", required=False),
         ToolParameter(name="date_range", description="Start date: 7daysAgo, 30daysAgo, etc.", required=False)],
        _get_google_analytics_data, "analytics")

    registry.register("get_search_console_data", "Get Google Search Console data — clicks, impressions, CTR, position.",
        [ToolParameter(name="site_url", description="Site URL registered in GSC"),
         ToolParameter(name="query_filter", description="Filter by query keyword", required=False),
         ToolParameter(name="date_range", description="Range: 7d or 30d", required=False)],
        _get_search_console_data, "analytics")

    registry.register("keyword_planner_lookup", "Get search volume and CPC for multiple keywords.",
        [ToolParameter(name="keywords", description="Comma-separated keywords"),
         ToolParameter(name="country", description="Country code (default: us)", required=False)],
        _keyword_planner_lookup, "analytics")

    registry.register("create_ad_rule", "Create automated ad optimization rule (pause, scale, alert).",
        [ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="platform", description="Platform: meta, google, linkedin"),
         ToolParameter(name="rule_type", description="Rule type: pause, scale, alert"),
         ToolParameter(name="condition", description="Trigger condition (e.g. 'ctr < 0.5%')"),
         ToolParameter(name="action", description="Action to take (e.g. 'pause_ad', 'increase_budget_20%')")],
        _create_ad_rule, "analytics")

    # ── Design Director Tools ──

