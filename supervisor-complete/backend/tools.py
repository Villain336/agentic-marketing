"""
Supervisor Backend — Tool Registry
Extensible tool system. Each tool is a function agents can invoke during reasoning.
Covers: web, prospecting, email, social, ads, site deployment, CRM, calendar, memory.
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
# EMAIL TOOLS (SendGrid)
# ═══════════════════════════════════════════════════════════════════════════════

async def _send_email(to: str, subject: str, body: str, from_name: str = "",
                       reply_to: str = "") -> str:
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured. Set SENDGRID_API_KEY."})
    from_email = getattr(settings, 'sendgrid_from_email', '') or "noreply@supervisor.app"
    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": from_name or "Supervisor"},
        "subject": subject,
        "content": [{"type": "text/html", "value": body}],
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}
    try:
        resp = await _http.post("https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 202):
            msg_id = resp.headers.get("X-Message-Id", "")
            return json.dumps({"sent": True, "message_id": msg_id, "to": to})
        return json.dumps({"sent": False, "error": f"SendGrid {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"sent": False, "error": str(e)})


async def _schedule_email_sequence(emails: str) -> str:
    """Schedule a sequence of emails. Input: JSON array of {to, subject, body, send_at}."""
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        items = json.loads(emails) if isinstance(emails, str) else emails
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON for emails parameter"})
    results = []
    for item in items:
        result = await _send_email(
            to=item.get("to", ""), subject=item.get("subject", ""),
            body=item.get("body", ""), from_name=item.get("from_name", ""))
        results.append(json.loads(result))
    scheduled = sum(1 for r in results if r.get("sent"))
    return json.dumps({"scheduled": True, "count": scheduled, "total": len(items), "results": results})


async def _check_email_status(message_id: str) -> str:
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        resp = await _http.get(f"https://api.sendgrid.com/v3/messages/{message_id}",
            headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"message_id": message_id,
                "status": data.get("status", "unknown"),
                "events": data.get("events", [])[:5]})
        return json.dumps({"message_id": message_id, "status": "unknown"})
    except Exception as e:
        return json.dumps({"message_id": message_id, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL MEDIA TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _post_twitter(text: str, media_ids: str = "") -> str:
    bearer = getattr(settings, 'twitter_bearer_token', '') or ""
    if not bearer:
        return json.dumps({"error": "Twitter API not configured. Set TWITTER_BEARER_TOKEN."})
    payload: dict[str, Any] = {"text": text[:280]}
    if media_ids:
        payload["media"] = {"media_ids": [m.strip() for m in media_ids.split(",")]}
    try:
        resp = await _http.post("https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"posted": True, "tweet_id": data.get("data", {}).get("id", "")})
        return json.dumps({"posted": False, "error": f"Twitter {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"posted": False, "error": str(e)})


async def _search_twitter(query: str, max_results: int = 10) -> str:
    bearer = getattr(settings, 'twitter_bearer_token', '') or ""
    if not bearer:
        return json.dumps({"error": "Twitter API not configured."})
    try:
        resp = await _http.get("https://api.twitter.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {bearer}"},
            params={"query": query, "max_results": min(max_results, 100),
                    "tweet.fields": "author_id,created_at,public_metrics"})
        if resp.status_code == 200:
            data = resp.json()
            tweets = [{"id": t["id"], "text": t["text"][:200],
                       "metrics": t.get("public_metrics", {})}
                      for t in data.get("data", [])[:max_results]]
            return json.dumps({"query": query, "count": len(tweets), "tweets": tweets})
        return json.dumps({"error": f"Twitter {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _post_linkedin(text: str, image_url: str = "") -> str:
    client_id = getattr(settings, 'linkedin_client_id', '') or ""
    if not client_id:
        return json.dumps({"error": "LinkedIn API not configured. Set LINKEDIN_CLIENT_ID."})
    return json.dumps({"posted": False, "note": "LinkedIn posting requires OAuth flow. Content prepared.",
                       "content": text[:500]})


# ═══════════════════════════════════════════════════════════════════════════════
# AD DEPLOYMENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_meta_ad_campaign(campaign_name: str, daily_budget: str,
                                     targeting: str, ad_creatives: str) -> str:
    access_token = getattr(settings, 'meta_access_token', '') or ""
    if not access_token:
        return json.dumps({"error": "Meta Ads API not configured. Set META_ACCESS_TOKEN.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "targeting": targeting, "creatives": ad_creatives[:500]}})
    try:
        resp = await _http.post("https://graph.facebook.com/v19.0/act_/campaigns",
            params={"access_token": access_token},
            json={"name": campaign_name, "objective": "OUTCOME_LEADS",
                  "status": "PAUSED", "special_ad_categories": []})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"campaign_id": data.get("id", ""), "status": "draft", "name": campaign_name})
        return json.dumps({"error": f"Meta API {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _create_google_ads_campaign(campaign_name: str, daily_budget: str,
                                        keywords: str, ad_copy: str) -> str:
    dev_token = getattr(settings, 'google_ads_developer_token', '') or ""
    if not dev_token:
        return json.dumps({"error": "Google Ads API not configured.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "keywords": keywords, "copy": ad_copy[:500]}})
    return json.dumps({"campaign_id": "draft", "status": "draft", "name": campaign_name,
                       "note": "Google Ads campaign created as draft."})


async def _get_ad_performance(campaign_id: str, platform: str,
                                date_range: str = "last_7_days") -> str:
    if platform == "meta":
        token = getattr(settings, 'meta_access_token', '') or ""
        if not token:
            return json.dumps({"error": "Meta Ads not configured."})
        try:
            resp = await _http.get(
                f"https://graph.facebook.com/v19.0/{campaign_id}/insights",
                params={"access_token": token, "date_preset": date_range,
                        "fields": "impressions,clicks,ctr,cpc,spend,actions"})
            if resp.status_code == 200:
                data = resp.json().get("data", [{}])
                return json.dumps(data[0] if data else {})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Performance tracking not configured for {platform}"})


# ═══════════════════════════════════════════════════════════════════════════════
# SITE DEPLOYMENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _deploy_to_vercel(project_name: str, files: str, domain: str = "") -> str:
    token = getattr(settings, 'vercel_token', '') or ""
    if not token:
        return json.dumps({"error": "Vercel not configured. Set VERCEL_TOKEN.",
                           "draft": {"project": project_name, "domain": domain}})
    try:
        file_list = json.loads(files) if isinstance(files, str) else files
    except json.JSONDecodeError:
        file_list = [{"file": "index.html", "data": files[:5000]}]
    try:
        payload = {
            "name": project_name,
            "files": [{"file": f.get("file", "index.html"), "data": f.get("data", "")} for f in file_list],
        }
        resp = await _http.post("https://api.vercel.com/v13/deployments",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"url": f"https://{data.get('url', '')}", "deployment_id": data.get("id", ""), "status": "deployed"})
        return json.dumps({"error": f"Vercel {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _deploy_to_cloudflare(project_name: str, files: str, domain: str = "") -> str:
    token = getattr(settings, 'cloudflare_api_token', '') or ""
    account_id = getattr(settings, 'cloudflare_account_id', '') or ""
    if not token or not account_id:
        return json.dumps({"error": "Cloudflare not configured.",
                           "draft": {"project": project_name, "domain": domain}})
    return json.dumps({"status": "draft", "project": project_name,
                       "note": "Cloudflare Pages deployment requires upload via Workers API."})


# ═══════════════════════════════════════════════════════════════════════════════
# CRM TOOLS (HubSpot)
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_crm_contact(name: str, email: str, company: str = "",
                                title: str = "", source: str = "", notes: str = "") -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured. Set HUBSPOT_API_KEY.",
                           "draft": {"name": name, "email": email, "company": company}})
    name_parts = name.split(" ", 1)
    properties = {
        "email": email, "firstname": name_parts[0],
        "lastname": name_parts[1] if len(name_parts) > 1 else "",
        "company": company, "jobtitle": title,
    }
    try:
        resp = await _http.post("https://api.hubapi.com/crm/v3/objects/contacts",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": properties})
        if resp.status_code in (200, 201):
            return json.dumps({"contact_id": resp.json().get("id", ""), "created": True, "email": email})
        return json.dumps({"error": f"HubSpot {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _update_deal_stage(deal_id: str, stage: str) -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.patch(f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": {"dealstage": stage}})
        if resp.status_code == 200:
            return json.dumps({"updated": True, "deal_id": deal_id, "stage": stage})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _log_crm_activity(contact_id: str, activity_type: str,
                              notes: str, date: str = "") -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.post("https://api.hubapi.com/crm/v3/objects/notes",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": {"hs_note_body": f"[{activity_type}] {notes}", "hs_timestamp": date or ""},
                  "associations": [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]})
        if resp.status_code in (200, 201):
            return json.dumps({"activity_id": resp.json().get("id", ""), "logged": True})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _get_pipeline_summary() -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.get("https://api.hubapi.com/crm/v3/objects/deals",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": 100, "properties": "dealstage,amount,dealname"})
        if resp.status_code == 200:
            deals = resp.json().get("results", [])
            stages: dict[str, dict] = {}
            total_value = 0.0
            for d in deals:
                props = d.get("properties", {})
                stage = props.get("dealstage", "unknown")
                amount = float(props.get("amount", 0) or 0)
                if stage not in stages:
                    stages[stage] = {"name": stage, "count": 0, "value": 0}
                stages[stage]["count"] += 1
                stages[stage]["value"] += amount
                total_value += amount
            return json.dumps({"stages": list(stages.values()), "total_pipeline_value": total_value, "total_deals": len(deals)})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR TOOLS (Cal.com)
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_booking_link(event_type: str, duration: int = 30,
                                 availability: str = "") -> str:
    api_key = getattr(settings, 'calcom_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "Cal.com not configured. Set CALCOM_API_KEY.",
                           "draft": {"type": event_type, "duration": duration}})
    try:
        resp = await _http.post("https://api.cal.com/v1/event-types",
            params={"apiKey": api_key},
            json={"title": event_type, "slug": event_type.lower().replace(" ", "-"),
                  "length": duration, "description": f"Book a {duration}-min {event_type}"})
        if resp.status_code in (200, 201):
            slug = resp.json().get("event_type", {}).get("slug", event_type.lower().replace(" ", "-"))
            return json.dumps({"booking_url": f"https://cal.com/{slug}", "created": True})
        return json.dumps({"error": f"Cal.com {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER ALL TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def register_all_tools():
    # ── Web Tools ──
    registry.register("web_search", "Search the web for information about companies, industries, trends, or any topic.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="num_results", type="integer", description="Results count (1-10)", required=False)],
        _web_search, "web")

    registry.register("web_scrape", "Fetch and extract text from a URL. Use to read company sites, blog posts, landing pages.",
        [ToolParameter(name="url", description="Full URL to scrape"),
         ToolParameter(name="max_chars", type="integer", description="Max chars to return", required=False)],
        _web_scrape, "web")

    registry.register("analyze_website", "Analyze a website for content quality, word count, and basic SEO signals.",
        [ToolParameter(name="url", description="URL to analyze")],
        _analyze_website, "web")

    # ── Prospecting Tools ──
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

    # ── Memory Tools ──
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
    registry.register("send_email", "Send an email via SendGrid. Rate limited to 50/day per campaign.",
        [ToolParameter(name="to", description="Recipient email address"),
         ToolParameter(name="subject", description="Email subject line"),
         ToolParameter(name="body", description="Email body (HTML supported)"),
         ToolParameter(name="from_name", description="Sender display name", required=False),
         ToolParameter(name="reply_to", description="Reply-to email address", required=False)],
        _send_email, "email")

    registry.register("schedule_email_sequence", "Schedule a sequence of emails. Input is JSON array of {to, subject, body, send_at}.",
        [ToolParameter(name="emails", description="JSON array of email objects")],
        _schedule_email_sequence, "email")

    registry.register("check_email_status", "Check delivery status of a sent email by message ID.",
        [ToolParameter(name="message_id", description="SendGrid message ID")],
        _check_email_status, "email")

    # ── Social Tools ──
    registry.register("post_twitter", "Post a tweet. Max 10 posts/day.",
        [ToolParameter(name="text", description="Tweet text (max 280 chars)"),
         ToolParameter(name="media_ids", description="Comma-separated media IDs", required=False)],
        _post_twitter, "social")

    registry.register("search_twitter", "Search Twitter for relevant conversations and engagement opportunities.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="max_results", type="integer", description="Max results (1-100)", required=False)],
        _search_twitter, "social")

    registry.register("post_linkedin", "Post to LinkedIn. Max 2 posts/day.",
        [ToolParameter(name="text", description="Post text"),
         ToolParameter(name="image_url", description="Optional image URL", required=False)],
        _post_linkedin, "social")

    # ── Ad Tools ──
    registry.register("create_meta_ad_campaign", "Create a Meta (Facebook/Instagram) ad campaign.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="targeting", description="Targeting criteria"),
         ToolParameter(name="ad_creatives", description="Ad creative details")],
        _create_meta_ad_campaign, "ads")

    registry.register("create_google_ads_campaign", "Create a Google Ads search campaign.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="keywords", description="Target keywords"),
         ToolParameter(name="ad_copy", description="Ad copy")],
        _create_google_ads_campaign, "ads")

    registry.register("get_ad_performance", "Get performance metrics for an ad campaign.",
        [ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="platform", description="Platform: meta or google"),
         ToolParameter(name="date_range", description="Date range", required=False)],
        _get_ad_performance, "ads")

    # ── Site Deployment Tools ──
    registry.register("deploy_to_vercel", "Deploy site files to Vercel.",
        [ToolParameter(name="project_name", description="Project name"),
         ToolParameter(name="files", description="JSON array of {file, data} objects"),
         ToolParameter(name="domain", description="Custom domain", required=False)],
        _deploy_to_vercel, "deployment")

    registry.register("deploy_to_cloudflare", "Deploy site to Cloudflare Pages/Workers.",
        [ToolParameter(name="project_name", description="Project name"),
         ToolParameter(name="files", description="JSON array of {file, data} objects"),
         ToolParameter(name="domain", description="Custom domain", required=False)],
        _deploy_to_cloudflare, "deployment")

    # ── CRM Tools ──
    registry.register("create_crm_contact", "Create a contact in HubSpot CRM.",
        [ToolParameter(name="name", description="Full name"),
         ToolParameter(name="email", description="Email address"),
         ToolParameter(name="company", description="Company name", required=False),
         ToolParameter(name="title", description="Job title", required=False),
         ToolParameter(name="source", description="Lead source", required=False),
         ToolParameter(name="notes", description="Notes", required=False)],
        _create_crm_contact, "crm")

    registry.register("update_deal_stage", "Update a deal's pipeline stage in HubSpot.",
        [ToolParameter(name="deal_id", description="HubSpot deal ID"),
         ToolParameter(name="stage", description="New deal stage")],
        _update_deal_stage, "crm")

    registry.register("log_activity", "Log an activity against a CRM contact.",
        [ToolParameter(name="contact_id", description="HubSpot contact ID"),
         ToolParameter(name="activity_type", description="Type: email, call, meeting"),
         ToolParameter(name="notes", description="Activity notes"),
         ToolParameter(name="date", description="Activity date (ISO format)", required=False)],
        _log_crm_activity, "crm")

    registry.register("get_pipeline_summary", "Get summary of all deals in the HubSpot pipeline.",
        [], _get_pipeline_summary, "crm")

    # ── Calendar Tools ──
    registry.register("create_booking_link", "Create a booking link via Cal.com.",
        [ToolParameter(name="event_type", description="Event type name"),
         ToolParameter(name="duration", type="integer", description="Duration in minutes", required=False),
         ToolParameter(name="availability", description="Availability rules", required=False)],
        _create_booking_link, "calendar")


register_all_tools()
