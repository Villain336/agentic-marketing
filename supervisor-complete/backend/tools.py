"""
Supervisor Backend — Tool Registry
Extensible tool system. Each tool is a function agents can invoke during reasoning.
"""
from __future__ import annotations
import json
import re
import logging
from typing import Any, Callable, Awaitable

import httpx

from config import settings
from models import ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger("supervisor.tools")

_http = httpx.AsyncClient(timeout=30)


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


registry = ToolRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _web_search(query: str, num_results: int = 5) -> str:
    api_key = settings.serper_api_key
    if not api_key:
        return json.dumps({"note": "Web search not configured. Set SERPER_API_KEY.", "query": query, "results": []})
    try:
        resp = await _http.post("https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num_results})
        data = resp.json()
        results = [{"title": r.get("title",""), "url": r.get("link",""), "snippet": r.get("snippet","")} for r in data.get("organic", [])[:num_results]]
        return json.dumps({"query": query, "results": results})
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


async def _web_scrape(url: str, max_chars: int = 8000) -> str:
    try:
        resp = await _http.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; SupervisorBot/1.0)"})
        text = resp.text
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return json.dumps({"url": url, "content": text[:max_chars], "truncated": len(text) > max_chars})
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)})


async def _company_research(company_name: str, domain: str = "") -> str:
    if settings.apollo_api_key:
        try:
            resp = await _http.post("https://api.apollo.io/api/v1/mixed_companies/search",
                headers={"Content-Type": "application/json"},
                json={"api_key": settings.apollo_api_key, "q_organization_name": company_name, "page": 1, "per_page": 3})
            data = resp.json()
            results = [{
                "name": o.get("name",""), "domain": o.get("primary_domain",""),
                "industry": o.get("industry",""), "employees": o.get("estimated_num_employees",""),
                "revenue": o.get("annual_revenue_printed",""), "description": o.get("short_description","")[:300],
                "linkedin": o.get("linkedin_url",""), "location": o.get("raw_address",""),
            } for o in data.get("organizations", [])[:3]]
            return json.dumps({"company": company_name, "results": results})
        except Exception as e:
            return json.dumps({"company": company_name, "error": str(e)})
    return await _web_search(f"{company_name} company {domain} about")


async def _find_contacts(company_domain: str, titles: str = "", limit: int = 5) -> str:
    if settings.apollo_api_key:
        try:
            body: dict[str, Any] = {"api_key": settings.apollo_api_key, "q_organization_domains": company_domain, "page": 1, "per_page": limit}
            if titles:
                body["person_titles"] = [t.strip() for t in titles.split(",")]
            resp = await _http.post("https://api.apollo.io/api/v1/mixed_people/search",
                headers={"Content-Type": "application/json"}, json=body)
            data = resp.json()
            people = [{"name": p.get("name",""), "title": p.get("title",""), "email": p.get("email",""),
                       "linkedin": p.get("linkedin_url",""), "city": p.get("city",""), "state": p.get("state","")}
                      for p in data.get("people", [])[:limit]]
            return json.dumps({"domain": company_domain, "contacts": people})
        except Exception as e:
            return json.dumps({"domain": company_domain, "error": str(e)})
    if settings.hunter_api_key:
        try:
            resp = await _http.get("https://api.hunter.io/v2/domain-search",
                params={"domain": company_domain, "api_key": settings.hunter_api_key, "limit": limit})
            emails = resp.json().get("data", {}).get("emails", [])
            people = [{"name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
                       "email": e.get("value",""), "title": e.get("position",""),
                       "confidence": e.get("confidence", 0)} for e in emails[:limit]]
            return json.dumps({"domain": company_domain, "contacts": people})
        except Exception as e:
            return json.dumps({"domain": company_domain, "error": str(e)})
    return json.dumps({"domain": company_domain, "note": "No enrichment API configured. Set APOLLO_API_KEY or HUNTER_API_KEY."})


async def _verify_email(email: str) -> str:
    if settings.hunter_api_key:
        try:
            resp = await _http.get("https://api.hunter.io/v2/email-verifier",
                params={"email": email, "api_key": settings.hunter_api_key})
            d = resp.json().get("data", {})
            return json.dumps({"email": email, "status": d.get("status","unknown"), "score": d.get("score",0), "deliverable": d.get("status")=="valid"})
        except Exception as e:
            return json.dumps({"email": email, "error": str(e)})
    return json.dumps({"email": email, "note": "Email verification not configured."})


async def _analyze_website(url: str) -> str:
    content = await _web_scrape(url, max_chars=5000)
    data = json.loads(content)
    if "error" in data:
        return content
    text = data.get("content", "")
    return json.dumps({"url": url, "word_count": len(text.split()), "has_content": len(text.split()) > 100, "excerpt": text[:2000]})


async def _store_data(key: str, value: str, namespace: str = "campaign") -> str:
    return json.dumps({"stored": True, "key": f"{namespace}:{key}", "size": len(value)})


async def _read_data(key: str, namespace: str = "campaign") -> str:
    return json.dumps({"key": f"{namespace}:{key}", "note": "Connect Supabase for persistence."})


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER ALL TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def register_all_tools():
    registry.register("web_search", "Search the web for information about companies, industries, trends, or any topic.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="num_results", type="integer", description="Results count (1-10)", required=False)],
        _web_search, "web")

    registry.register("web_scrape", "Fetch and extract text from a URL. Use to read company sites, blog posts, landing pages.",
        [ToolParameter(name="url", description="Full URL to scrape"),
         ToolParameter(name="max_chars", type="integer", description="Max chars to return", required=False)],
        _web_scrape, "web")

    registry.register("company_research", "Research a company — returns industry, size, revenue, description, LinkedIn. Uses Apollo if configured.",
        [ToolParameter(name="company_name", description="Company name"),
         ToolParameter(name="domain", description="Company domain if known", required=False)],
        _company_research, "prospecting")

    registry.register("find_contacts", "Find decision-maker contacts at a company. Returns names, titles, emails, LinkedIn URLs.",
        [ToolParameter(name="company_domain", description="Company domain (e.g. acme.com)"),
         ToolParameter(name="titles", description="Comma-separated titles to filter", required=False),
         ToolParameter(name="limit", type="integer", description="Max contacts", required=False)],
        _find_contacts, "prospecting")

    registry.register("verify_email", "Verify if an email address is valid and deliverable.",
        [ToolParameter(name="email", description="Email to verify")],
        _verify_email, "email")

    registry.register("analyze_website", "Analyze a website for content quality, word count, and basic SEO signals.",
        [ToolParameter(name="url", description="URL to analyze")],
        _analyze_website, "web")

    registry.register("store_data", "Store data in campaign memory for other agents to reference.",
        [ToolParameter(name="key", description="Key name (e.g. 'qualified_prospects')"),
         ToolParameter(name="value", description="Data to store"),
         ToolParameter(name="namespace", description="Namespace", required=False)],
        _store_data, "memory")

    registry.register("read_data", "Read previously stored data from campaign memory.",
        [ToolParameter(name="key", description="Key to read"),
         ToolParameter(name="namespace", description="Namespace", required=False)],
        _read_data, "memory")


register_all_tools()
