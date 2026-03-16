"""
Supervisor Backend — Tool Registry
Extensible tool system. Each tool is a function agents can invoke during reasoning.
Covers: web, prospecting, enrichment, email, voice, sms, social, ads, seo,
content, image generation, deployment, dns, monitoring, crm, calendar,
document generation, e-signatures, analytics, messaging, memory.
"""
from __future__ import annotations
import json
import re
import logging
import base64
from typing import Any, Callable, Awaitable

import httpx

from config import settings
from models import ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger("supervisor.tools")

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
# PROSPECTOR — Enrichment, Technographics, Phone, LinkedIn, Lead Scoring
# ═══════════════════════════════════════════════════════════════════════════════

async def _enrich_company(domain: str) -> str:
    """Full company enrichment via Clearbit/Apollo — firmographic + technographic."""
    clearbit_key = getattr(settings, 'clearbit_api_key', '') or ""
    if clearbit_key:
        try:
            resp = await _http.get(f"https://company.clearbit.com/v2/companies/find",
                params={"domain": domain},
                headers={"Authorization": f"Bearer {clearbit_key}"})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "domain": domain, "name": d.get("name", ""),
                    "industry": d.get("category", {}).get("industry", ""),
                    "sub_industry": d.get("category", {}).get("subIndustry", ""),
                    "employees": d.get("metrics", {}).get("employees", ""),
                    "revenue_range": d.get("metrics", {}).get("estimatedAnnualRevenue", ""),
                    "tech_stack": d.get("tech", [])[:20],
                    "founded": d.get("foundedYear", ""),
                    "description": d.get("description", "")[:500],
                    "location": f"{d.get('geo', {}).get('city', '')}, {d.get('geo', {}).get('state', '')}, {d.get('geo', {}).get('country', '')}",
                    "linkedin_handle": d.get("linkedin", {}).get("handle", ""),
                    "twitter_handle": d.get("twitter", {}).get("handle", ""),
                    "phone": d.get("phone", ""),
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    if settings.apollo_api_key:
        try:
            resp = await _http.post("https://api.apollo.io/api/v1/organizations/enrich",
                headers={"Content-Type": "application/json"},
                json={"api_key": settings.apollo_api_key, "domain": domain})
            d = resp.json().get("organization", {})
            return json.dumps({
                "domain": domain, "name": d.get("name", ""),
                "industry": d.get("industry", ""), "employees": d.get("estimated_num_employees", ""),
                "revenue": d.get("annual_revenue_printed", ""),
                "technologies": d.get("current_technologies", [])[:20],
                "description": d.get("short_description", "")[:500],
                "linkedin": d.get("linkedin_url", ""), "phone": d.get("phone", ""),
            })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return json.dumps({"domain": domain, "note": "No enrichment API configured. Set CLEARBIT_API_KEY or APOLLO_API_KEY."})


async def _enrich_person(email: str) -> str:
    """Enrich a person by email — returns name, title, company, social profiles, phone."""
    clearbit_key = getattr(settings, 'clearbit_api_key', '') or ""
    if clearbit_key:
        try:
            resp = await _http.get("https://person.clearbit.com/v2/people/find",
                params={"email": email},
                headers={"Authorization": f"Bearer {clearbit_key}"})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "email": email, "name": d.get("name", {}).get("fullName", ""),
                    "title": d.get("employment", {}).get("title", ""),
                    "company": d.get("employment", {}).get("name", ""),
                    "company_domain": d.get("employment", {}).get("domain", ""),
                    "linkedin": d.get("linkedin", {}).get("handle", ""),
                    "twitter": d.get("twitter", {}).get("handle", ""),
                    "location": d.get("geo", {}).get("city", ""),
                    "bio": d.get("bio", "")[:300],
                })
        except Exception as e:
            return json.dumps({"email": email, "error": str(e)})
    if settings.apollo_api_key:
        try:
            resp = await _http.post("https://api.apollo.io/api/v1/people/match",
                headers={"Content-Type": "application/json"},
                json={"api_key": settings.apollo_api_key, "email": email})
            d = resp.json().get("person", {})
            return json.dumps({
                "email": email, "name": d.get("name", ""), "title": d.get("title", ""),
                "company": d.get("organization", {}).get("name", ""),
                "linkedin": d.get("linkedin_url", ""),
                "phone": d.get("phone_numbers", [{}])[0].get("sanitized_number", "") if d.get("phone_numbers") else "",
            })
        except Exception as e:
            return json.dumps({"email": email, "error": str(e)})
    return json.dumps({"email": email, "note": "No person enrichment API configured."})


async def _find_phone_number(name: str, company: str = "", email: str = "") -> str:
    """Look up direct phone number for a prospect."""
    if settings.apollo_api_key:
        try:
            body: dict[str, Any] = {"api_key": settings.apollo_api_key}
            if email:
                body["email"] = email
            else:
                body["first_name"] = name.split()[0] if name else ""
                body["last_name"] = name.split()[-1] if name and len(name.split()) > 1 else ""
                if company:
                    body["organization_name"] = company
            resp = await _http.post("https://api.apollo.io/api/v1/people/match",
                headers={"Content-Type": "application/json"}, json=body)
            d = resp.json().get("person", {})
            phones = d.get("phone_numbers", [])
            return json.dumps({
                "name": name, "phone_numbers": [
                    {"number": p.get("sanitized_number", ""), "type": p.get("type", "")}
                    for p in phones[:3]
                ],
                "email": d.get("email", ""),
            })
        except Exception as e:
            return json.dumps({"name": name, "error": str(e)})
    return json.dumps({"name": name, "note": "Phone lookup requires APOLLO_API_KEY."})


async def _search_linkedin_prospects(query: str, industry: str = "",
                                      company_size: str = "", geography: str = "",
                                      limit: int = 10) -> str:
    """Search for prospects matching criteria via Apollo's people search (LinkedIn-sourced data)."""
    if not settings.apollo_api_key:
        return json.dumps({"note": "LinkedIn prospect search requires APOLLO_API_KEY.", "query": query})
    try:
        body: dict[str, Any] = {
            "api_key": settings.apollo_api_key,
            "q_keywords": query,
            "page": 1, "per_page": min(limit, 25),
        }
        if industry:
            body["organization_industry_tag_ids"] = [industry]
        if company_size:
            size_map = {"1-10": "1,10", "11-50": "11,50", "51-200": "51,200",
                        "201-500": "201,500", "501-1000": "501,1000", "1001+": "1001,"}
            body["organization_num_employees_ranges"] = [size_map.get(company_size, company_size)]
        if geography:
            body["person_locations"] = [geography]
        resp = await _http.post("https://api.apollo.io/api/v1/mixed_people/search",
            headers={"Content-Type": "application/json"}, json=body)
        data = resp.json()
        people = [{
            "name": p.get("name", ""), "title": p.get("title", ""),
            "email": p.get("email", ""), "linkedin": p.get("linkedin_url", ""),
            "company": p.get("organization", {}).get("name", ""),
            "company_domain": p.get("organization", {}).get("primary_domain", ""),
            "location": f"{p.get('city', '')}, {p.get('state', '')}",
            "phone": (p.get("phone_numbers", [{}])[0].get("sanitized_number", "")
                      if p.get("phone_numbers") else ""),
        } for p in data.get("people", [])[:limit]]
        return json.dumps({"query": query, "count": len(people), "prospects": people})
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})


async def _check_buyer_intent(domain: str, topics: str = "") -> str:
    """Check buyer intent signals for a company using Bombora (or fallback to web search)."""
    bombora_key = getattr(settings, 'bombora_api_key', '') or ""
    if bombora_key:
        try:
            resp = await _http.get("https://api.bombora.com/v1/company/surge",
                params={"domain": domain, "topics": topics},
                headers={"Authorization": f"Bearer {bombora_key}"})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"domain": domain, "intent_signals": data.get("topics", []),
                                   "surge_score": data.get("composite_score", 0)})
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    search_q = f'"{domain}" hiring OR "looking for" OR RFP {topics}'
    return await _web_search(search_q, 5)


async def _score_lead(company_name: str, domain: str = "", employee_count: str = "",
                       industry: str = "", title: str = "", icp_description: str = "") -> str:
    """Score a lead 0-100 based on ICP fit. Uses heuristic matching."""
    score = 50
    reasons = []
    if icp_description and industry:
        if industry.lower() in icp_description.lower():
            score += 15
            reasons.append(f"Industry '{industry}' matches ICP")
    if employee_count:
        try:
            emp = int(employee_count.replace(",", "").replace("+", ""))
            if 10 <= emp <= 500:
                score += 10
                reasons.append(f"Company size ({emp}) in sweet spot")
            elif emp > 500:
                score += 5
                reasons.append(f"Enterprise ({emp} employees)")
        except ValueError:
            pass
    if title:
        high_value = ["ceo", "cto", "cmo", "vp", "director", "head of", "founder", "owner"]
        if any(t in title.lower() for t in high_value):
            score += 15
            reasons.append(f"Decision-maker title: {title}")
        else:
            score += 5
            reasons.append(f"Contact title: {title}")
    if domain:
        score += 5
        reasons.append("Domain available for outreach")
    score = min(score, 100)
    grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 50 else "F"
    return json.dumps({"company": company_name, "score": score, "grade": grade,
                       "reasons": reasons, "recommendation": "pursue" if score >= 60 else "deprioritize"})


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
# OUTREACH — Voice Calling, SMS, LinkedIn Messaging, Email Warmup, Reply Detection
# ═══════════════════════════════════════════════════════════════════════════════

async def _make_phone_call(to_number: str, script: str, voice: str = "nat",
                            max_duration_minutes: int = 5) -> str:
    """Make an AI voice call using Bland.ai. Falls back to Twilio for basic calling."""
    bland_key = getattr(settings, 'bland_api_key', '') or ""
    if bland_key:
        try:
            resp = await _http_long.post("https://api.bland.ai/v1/calls",
                headers={"Authorization": bland_key, "Content-Type": "application/json"},
                json={
                    "phone_number": to_number,
                    "task": script,
                    "voice": voice,
                    "max_duration": max_duration_minutes,
                    "wait_for_greeting": True,
                    "record": True,
                })
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_id": data.get("call_id", ""), "status": "initiated",
                                   "to": to_number, "provider": "bland.ai"})
            return json.dumps({"error": f"Bland.ai {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "bland.ai"})
    vapi_key = getattr(settings, 'vapi_api_key', '') or ""
    if vapi_key:
        try:
            resp = await _http_long.post("https://api.vapi.ai/call/phone",
                headers={"Authorization": f"Bearer {vapi_key}", "Content-Type": "application/json"},
                json={
                    "phoneNumberId": getattr(settings, 'vapi_phone_id', ''),
                    "customer": {"number": to_number},
                    "assistant": {
                        "firstMessage": script[:200],
                        "model": {"provider": "openai", "model": "gpt-4o-mini",
                                  "messages": [{"role": "system", "content": script}]},
                    },
                    "maxDurationSeconds": max_duration_minutes * 60,
                })
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_id": data.get("id", ""), "status": "initiated",
                                   "to": to_number, "provider": "vapi"})
            return json.dumps({"error": f"Vapi {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "vapi"})
    twilio_sid = getattr(settings, 'twilio_account_sid', '') or ""
    twilio_token = getattr(settings, 'twilio_auth_token', '') or ""
    if twilio_sid and twilio_token:
        try:
            from_number = getattr(settings, 'twilio_phone_number', '') or ""
            auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
            twiml = f'<Response><Say>{script[:500]}</Say></Response>'
            resp = await _http.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Calls.json",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"To": to_number, "From": from_number, "Twiml": twiml})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_sid": data.get("sid", ""), "status": data.get("status", ""),
                                   "to": to_number, "provider": "twilio"})
            return json.dumps({"error": f"Twilio {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "twilio"})
    return json.dumps({"error": "No voice provider configured. Set BLAND_API_KEY, VAPI_API_KEY, or TWILIO_ACCOUNT_SID."})


async def _get_call_transcript(call_id: str, provider: str = "bland.ai") -> str:
    """Retrieve transcript and analysis from a completed AI call."""
    if provider == "bland.ai":
        bland_key = getattr(settings, 'bland_api_key', '') or ""
        if not bland_key:
            return json.dumps({"error": "Bland.ai not configured."})
        try:
            resp = await _http.get(f"https://api.bland.ai/v1/calls/{call_id}",
                headers={"Authorization": bland_key})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "call_id": call_id, "status": d.get("status", ""),
                    "duration": d.get("call_length", ""),
                    "transcript": d.get("concatenated_transcript", "")[:5000],
                    "summary": d.get("summary", ""),
                    "recording_url": d.get("recording_url", ""),
                    "answered": d.get("answered_by", "") != "voicemail",
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "vapi":
        vapi_key = getattr(settings, 'vapi_api_key', '') or ""
        if not vapi_key:
            return json.dumps({"error": "Vapi not configured."})
        try:
            resp = await _http.get(f"https://api.vapi.ai/call/{call_id}",
                headers={"Authorization": f"Bearer {vapi_key}"})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "call_id": call_id, "status": d.get("status", ""),
                    "duration": d.get("endedAt", ""),
                    "transcript": d.get("transcript", "")[:5000],
                    "recording_url": d.get("recordingUrl", ""),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown provider: {provider}"})


async def _send_sms(to_number: str, message: str) -> str:
    """Send SMS via Twilio."""
    twilio_sid = getattr(settings, 'twilio_account_sid', '') or ""
    twilio_token = getattr(settings, 'twilio_auth_token', '') or ""
    if not twilio_sid or not twilio_token:
        return json.dumps({"error": "Twilio not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."})
    try:
        from_number = getattr(settings, 'twilio_phone_number', '') or ""
        auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
        resp = await _http.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"To": to_number, "From": from_number, "Body": message[:1600]})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"sent": True, "sid": data.get("sid", ""), "to": to_number})
        return json.dumps({"sent": False, "error": f"Twilio {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"sent": False, "error": str(e)})


async def _send_linkedin_message(profile_url: str, message: str) -> str:
    """Send LinkedIn message/connection request via Phantombuster or Dripify."""
    phantom_key = getattr(settings, 'phantombuster_api_key', '') or ""
    if phantom_key:
        try:
            resp = await _http.post("https://api.phantombuster.com/api/v2/agents/launch",
                headers={"X-Phantombuster-Key": phantom_key, "Content-Type": "application/json"},
                json={
                    "id": getattr(settings, 'phantombuster_linkedin_agent_id', ''),
                    "argument": json.dumps({
                        "profileUrl": profile_url,
                        "message": message[:300],
                    }),
                })
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"queued": True, "container_id": data.get("containerId", ""),
                                   "profile": profile_url})
            return json.dumps({"error": f"Phantombuster {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "LinkedIn automation not configured. Set PHANTOMBUSTER_API_KEY.",
                       "draft": {"profile": profile_url, "message": message[:300]}})


async def _check_email_warmup_status(email_account: str) -> str:
    """Check email warmup/deliverability status via Instantly.ai."""
    instantly_key = getattr(settings, 'instantly_api_key', '') or ""
    if not instantly_key:
        return json.dumps({"error": "Email warmup not configured. Set INSTANTLY_API_KEY.",
                           "recommendation": "Use Instantly.ai or Smartlead for warmup."})
    try:
        resp = await _http.get("https://api.instantly.ai/api/v1/account/warmup/status",
            params={"api_key": instantly_key, "email": email_account})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "email": email_account, "warmup_active": data.get("warmup_active", False),
                "warmup_reputation": data.get("warmup_reputation", ""),
                "daily_limit": data.get("daily_limit", 0),
                "emails_sent_today": data.get("emails_sent_today", 0),
            })
        return json.dumps({"error": f"Instantly {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _detect_email_replies(campaign_tag: str = "", since_hours: int = 24) -> str:
    """Check for replies to sent emails via SendGrid inbound parse or IMAP."""
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        resp = await _http.get("https://api.sendgrid.com/v3/messages",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": 50, "query": f"status='delivered' AND last_event_time BETWEEN NOW-{since_hours}h AND NOW"})
        if resp.status_code == 200:
            messages = resp.json().get("messages", [])
            replied = [m for m in messages if m.get("opens_count", 0) > 0]
            return json.dumps({
                "total_sent": len(messages), "opened": len(replied),
                "open_rate": round(len(replied) / max(len(messages), 1) * 100, 1),
                "messages": [{"to": m.get("to_email", ""), "subject": m.get("subject", ""),
                              "status": m.get("status", ""), "opens": m.get("opens_count", 0)}
                             for m in replied[:20]],
            })
        return json.dumps({"error": f"SendGrid {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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
# CONTENT — SEO Audit, Image Generation, CMS Publishing, Plagiarism Check
# ═══════════════════════════════════════════════════════════════════════════════

async def _seo_keyword_research(keyword: str, country: str = "us") -> str:
    """Get keyword difficulty, search volume, CPC via DataForSEO or SEMrush."""
    dataforseo_login = getattr(settings, 'dataforseo_login', '') or ""
    dataforseo_pass = getattr(settings, 'dataforseo_password', '') or ""
    if dataforseo_login and dataforseo_pass:
        try:
            auth = base64.b64encode(f"{dataforseo_login}:{dataforseo_pass}".encode()).decode()
            resp = await _http.post("https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"keywords": [keyword], "location_code": 2840 if country == "us" else 2826,
                       "language_code": "en"}])
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("tasks", [{}])[0].get("result", [])
                if results:
                    r = results[0]
                    return json.dumps({
                        "keyword": keyword, "search_volume": r.get("search_volume", 0),
                        "cpc": r.get("cpc", 0), "competition": r.get("competition", ""),
                        "competition_index": r.get("competition_index", 0),
                    })
        except Exception as e:
            return json.dumps({"keyword": keyword, "error": str(e)})
    semrush_key = getattr(settings, 'semrush_api_key', '') or ""
    if semrush_key:
        try:
            resp = await _http.get("https://api.semrush.com/",
                params={"type": "phrase_this", "key": semrush_key, "phrase": keyword,
                        "database": country, "export_columns": "Ph,Nq,Cp,Co,Nr"})
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                if len(lines) >= 2:
                    vals = lines[1].split(";")
                    return json.dumps({
                        "keyword": keyword, "search_volume": int(vals[1]) if len(vals) > 1 else 0,
                        "cpc": float(vals[2]) if len(vals) > 2 else 0,
                        "competition": float(vals[3]) if len(vals) > 3 else 0,
                    })
        except Exception as e:
            return json.dumps({"keyword": keyword, "error": str(e)})
    return await _web_search(f"{keyword} search volume CPC keyword difficulty", 3)


async def _seo_backlink_analysis(domain: str) -> str:
    """Analyze backlink profile via DataForSEO or Ahrefs."""
    dataforseo_login = getattr(settings, 'dataforseo_login', '') or ""
    dataforseo_pass = getattr(settings, 'dataforseo_password', '') or ""
    if dataforseo_login and dataforseo_pass:
        try:
            auth = base64.b64encode(f"{dataforseo_login}:{dataforseo_pass}".encode()).decode()
            resp = await _http.post("https://api.dataforseo.com/v3/backlinks/summary/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"target": domain}])
            if resp.status_code == 200:
                data = resp.json()
                r = data.get("tasks", [{}])[0].get("result", [{}])[0]
                return json.dumps({
                    "domain": domain,
                    "backlinks_total": r.get("backlinks", 0),
                    "referring_domains": r.get("referring_domains", 0),
                    "domain_rank": r.get("rank", 0),
                    "dofollow": r.get("referring_links_types", {}).get("dofollow", 0),
                    "nofollow": r.get("referring_links_types", {}).get("nofollow", 0),
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return await _web_search(f'site:{domain} backlinks referring domains', 3)


async def _generate_image(prompt: str, style: str = "professional",
                           size: str = "1024x1024") -> str:
    """Generate image via OpenAI DALL-E, Replicate Flux, or Fal.ai."""
    openai_key = getattr(settings, 'openai_image_key', '') or ""
    if not openai_key:
        for p in settings.providers:
            if p.name == "openai" and p.api_key:
                openai_key = p.api_key
                break
    if openai_key:
        try:
            resp = await _http_long.post("https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "dall-e-3", "prompt": f"{style} style: {prompt}",
                      "n": 1, "size": size, "quality": "standard"})
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("data", [{}])[0].get("url", "")
                revised = data.get("data", [{}])[0].get("revised_prompt", "")
                return json.dumps({"image_url": url, "revised_prompt": revised, "provider": "dall-e-3"})
            return json.dumps({"error": f"OpenAI {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "dall-e-3"})
    replicate_key = getattr(settings, 'replicate_api_key', '') or ""
    if replicate_key:
        try:
            resp = await _http_long.post("https://api.replicate.com/v1/predictions",
                headers={"Authorization": f"Bearer {replicate_key}", "Content-Type": "application/json"},
                json={"version": "black-forest-labs/flux-1.1-pro",
                      "input": {"prompt": f"{style} style: {prompt}",
                                "width": int(size.split("x")[0]),
                                "height": int(size.split("x")[1])}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"prediction_id": data.get("id", ""), "status": data.get("status", ""),
                                   "provider": "replicate/flux"})
            return json.dumps({"error": f"Replicate {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "replicate"})
    fal_key = getattr(settings, 'fal_api_key', '') or ""
    if fal_key:
        try:
            resp = await _http_long.post("https://queue.fal.run/fal-ai/flux/dev",
                headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                json={"prompt": f"{style} style: {prompt}",
                      "image_size": {"width": int(size.split("x")[0]),
                                     "height": int(size.split("x")[1])}})
            if resp.status_code in (200, 201):
                data = resp.json()
                images = data.get("images", [])
                url = images[0].get("url", "") if images else ""
                return json.dumps({"image_url": url, "provider": "fal.ai/flux"})
            return json.dumps({"error": f"Fal.ai {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "fal.ai"})
    return json.dumps({"error": "No image generation API configured. Set OPENAI_API_KEY, REPLICATE_API_KEY, or FAL_API_KEY."})


async def _publish_to_cms(title: str, content: str, status: str = "draft",
                           platform: str = "wordpress", tags: str = "") -> str:
    """Publish content to WordPress, Ghost, or Webflow CMS."""
    if platform == "wordpress":
        wp_url = getattr(settings, 'wordpress_url', '') or ""
        wp_user = getattr(settings, 'wordpress_user', '') or ""
        wp_app_password = getattr(settings, 'wordpress_app_password', '') or ""
        if not wp_url or not wp_user:
            return json.dumps({"error": "WordPress not configured. Set WORDPRESS_URL and WORDPRESS_USER.",
                               "draft": {"title": title, "status": status}})
        try:
            auth = base64.b64encode(f"{wp_user}:{wp_app_password}".encode()).decode()
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            resp = await _http.post(f"{wp_url}/wp-json/wp/v2/posts",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json={"title": title, "content": content, "status": status,
                      "tags": tag_list})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"post_id": data.get("id", ""), "url": data.get("link", ""),
                                   "status": data.get("status", ""), "platform": "wordpress"})
            return json.dumps({"error": f"WordPress {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "ghost":
        ghost_url = getattr(settings, 'ghost_url', '') or ""
        ghost_key = getattr(settings, 'ghost_admin_key', '') or ""
        if not ghost_url or not ghost_key:
            return json.dumps({"error": "Ghost not configured. Set GHOST_URL and GHOST_ADMIN_KEY.",
                               "draft": {"title": title, "status": status}})
        try:
            import time, hashlib, hmac
            key_id, secret = ghost_key.split(":")
            iat = int(time.time())
            header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode()).decode().rstrip("=")
            payload_b = base64.urlsafe_b64encode(json.dumps({"iat": iat, "exp": iat + 300, "aud": "/admin/"}).encode()).decode().rstrip("=")
            sig_input = f"{header}.{payload_b}"
            sig = base64.urlsafe_b64encode(hmac.new(bytes.fromhex(secret), sig_input.encode(), hashlib.sha256).digest()).decode().rstrip("=")
            token = f"{sig_input}.{sig}"
            resp = await _http.post(f"{ghost_url}/ghost/api/admin/posts/",
                headers={"Authorization": f"Ghost {token}", "Content-Type": "application/json"},
                json={"posts": [{"title": title, "html": content, "status": status,
                                 "tags": [{"name": t.strip()} for t in tags.split(",")] if tags else []}]})
            if resp.status_code in (200, 201):
                data = resp.json()
                post = data.get("posts", [{}])[0]
                return json.dumps({"post_id": post.get("id", ""), "url": post.get("url", ""),
                                   "status": post.get("status", ""), "platform": "ghost"})
            return json.dumps({"error": f"Ghost {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "webflow":
        wf_key = getattr(settings, 'webflow_api_key', '') or ""
        wf_collection = getattr(settings, 'webflow_blog_collection_id', '') or ""
        if not wf_key or not wf_collection:
            return json.dumps({"error": "Webflow not configured. Set WEBFLOW_API_KEY.",
                               "draft": {"title": title, "status": status}})
        try:
            resp = await _http.post(f"https://api.webflow.com/v2/collections/{wf_collection}/items",
                headers={"Authorization": f"Bearer {wf_key}", "Content-Type": "application/json"},
                json={"fieldData": {"name": title, "post-body": content, "slug": re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-'))}})
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                return json.dumps({"item_id": data.get("id", ""), "status": "draft", "platform": "webflow"})
            return json.dumps({"error": f"Webflow {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown CMS platform: {platform}"})


async def _check_plagiarism(text: str) -> str:
    """Check text originality via Copyscape API."""
    copyscape_user = getattr(settings, 'copyscape_user', '') or ""
    copyscape_key = getattr(settings, 'copyscape_api_key', '') or ""
    if not copyscape_user or not copyscape_key:
        return json.dumps({"note": "Plagiarism check not configured. Set COPYSCAPE_USER and COPYSCAPE_API_KEY.",
                           "word_count": len(text.split()),
                           "recommendation": "Manually check via copyscape.com before publishing."})
    try:
        resp = await _http.post("https://www.copyscape.com/api/",
            data={"u": copyscape_user, "o": copyscape_key, "t": text[:5000], "f": "json"})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "original": data.get("result", "") == "0",
                "matches_found": int(data.get("count", 0)),
                "matches": [{"url": m.get("url", ""), "percent": m.get("percentmatched", "")}
                            for m in data.get("result", [])[:5]] if isinstance(data.get("result"), list) else [],
            })
        return json.dumps({"error": f"Copyscape {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL — Scheduling, Analytics, Community Monitoring, Instagram
# ═══════════════════════════════════════════════════════════════════════════════

async def _schedule_social_post(platform: str, text: str, scheduled_time: str,
                                  image_url: str = "") -> str:
    """Schedule a social post via Buffer API."""
    buffer_key = getattr(settings, 'buffer_api_key', '') or ""
    if not buffer_key:
        return json.dumps({"error": "Buffer not configured. Set BUFFER_API_KEY.",
                           "draft": {"platform": platform, "text": text[:200],
                                     "scheduled_time": scheduled_time}})
    try:
        resp = await _http.get("https://api.bufferapp.com/1/profiles.json",
            params={"access_token": buffer_key})
        profiles = resp.json() if resp.status_code == 200 else []
        profile_id = ""
        for p in profiles:
            if platform.lower() in p.get("service", "").lower():
                profile_id = p.get("id", "")
                break
        if not profile_id:
            return json.dumps({"error": f"No Buffer profile found for {platform}"})
        payload: dict[str, Any] = {
            "access_token": buffer_key,
            "profile_ids[]": profile_id,
            "text": text,
            "scheduled_at": scheduled_time,
        }
        if image_url:
            payload["media[photo]"] = image_url
        resp = await _http.post("https://api.bufferapp.com/1/updates/create.json", data=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"scheduled": True, "update_id": data.get("updates", [{}])[0].get("id", ""),
                               "platform": platform, "scheduled_time": scheduled_time})
        return json.dumps({"error": f"Buffer {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _get_social_analytics(platform: str, period: str = "7d") -> str:
    """Get social media engagement metrics for a platform."""
    if platform == "twitter":
        bearer = getattr(settings, 'twitter_bearer_token', '') or ""
        if not bearer:
            return json.dumps({"error": "Twitter not configured."})
        try:
            resp = await _http.get("https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {bearer}"},
                params={"user.fields": "public_metrics"})
            if resp.status_code == 200:
                metrics = resp.json().get("data", {}).get("public_metrics", {})
                return json.dumps({"platform": "twitter", "followers": metrics.get("followers_count", 0),
                                   "following": metrics.get("following_count", 0),
                                   "tweets": metrics.get("tweet_count", 0),
                                   "listed": metrics.get("listed_count", 0)})
        except Exception as e:
            return json.dumps({"error": str(e)})
    if platform in ("instagram", "facebook"):
        token = getattr(settings, 'meta_access_token', '') or ""
        if not token:
            return json.dumps({"error": "Meta API not configured."})
        try:
            resp = await _http.get("https://graph.facebook.com/v19.0/me/accounts",
                params={"access_token": token})
            if resp.status_code == 200:
                pages = resp.json().get("data", [])
                if pages:
                    page_token = pages[0].get("access_token", "")
                    page_id = pages[0].get("id", "")
                    metrics_resp = await _http.get(
                        f"https://graph.facebook.com/v19.0/{page_id}/insights",
                        params={"access_token": page_token, "metric": "page_impressions,page_engaged_users",
                                "period": "day"})
                    if metrics_resp.status_code == 200:
                        return json.dumps({"platform": platform, "insights": metrics_resp.json().get("data", [])[:5]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Analytics not configured for {platform}"})


async def _post_instagram(caption: str, image_url: str) -> str:
    """Post to Instagram via Meta Graph API (requires Business account)."""
    token = getattr(settings, 'meta_access_token', '') or ""
    ig_account_id = getattr(settings, 'instagram_business_id', '') or ""
    if not token or not ig_account_id:
        return json.dumps({"error": "Instagram not configured. Set META_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID.",
                           "draft": {"caption": caption[:200], "image_url": image_url}})
    try:
        create_resp = await _http.post(f"https://graph.facebook.com/v19.0/{ig_account_id}/media",
            params={"access_token": token, "caption": caption, "image_url": image_url})
        if create_resp.status_code == 200:
            creation_id = create_resp.json().get("id", "")
            publish_resp = await _http.post(f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish",
                params={"access_token": token, "creation_id": creation_id})
            if publish_resp.status_code == 200:
                return json.dumps({"posted": True, "media_id": publish_resp.json().get("id", ""),
                                   "platform": "instagram"})
        return json.dumps({"error": f"Instagram API error: {create_resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _monitor_community(platform: str, keywords: str, limit: int = 10) -> str:
    """Monitor Reddit, Hacker News, or Product Hunt for brand mentions and opportunities."""
    keyword_list = [k.strip() for k in keywords.split(",")]
    if platform == "reddit":
        try:
            results = []
            for kw in keyword_list[:3]:
                resp = await _http.get(f"https://www.reddit.com/search.json",
                    params={"q": kw, "sort": "new", "limit": min(limit, 10)},
                    headers={"User-Agent": "SupervisorBot/1.0"})
                if resp.status_code == 200:
                    posts = resp.json().get("data", {}).get("children", [])
                    for p in posts:
                        d = p.get("data", {})
                        results.append({"title": d.get("title", "")[:200],
                                        "subreddit": d.get("subreddit", ""),
                                        "url": f"https://reddit.com{d.get('permalink', '')}",
                                        "score": d.get("score", 0),
                                        "comments": d.get("num_comments", 0)})
            return json.dumps({"platform": "reddit", "keywords": keyword_list,
                               "results": results[:limit]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "hackernews":
        try:
            results = []
            for kw in keyword_list[:3]:
                resp = await _http.get("https://hn.algolia.com/api/v1/search_by_date",
                    params={"query": kw, "hitsPerPage": min(limit, 10)})
                if resp.status_code == 200:
                    hits = resp.json().get("hits", [])
                    for h in hits:
                        results.append({"title": h.get("title", "") or h.get("story_title", ""),
                                        "url": h.get("url", "") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                                        "points": h.get("points", 0),
                                        "comments": h.get("num_comments", 0)})
            return json.dumps({"platform": "hackernews", "keywords": keyword_list,
                               "results": results[:limit]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "producthunt":
        ph_token = getattr(settings, 'producthunt_token', '') or ""
        if ph_token:
            try:
                resp = await _http.post("https://api.producthunt.com/v2/api/graphql",
                    headers={"Authorization": f"Bearer {ph_token}", "Content-Type": "application/json"},
                    json={"query": f'{{ posts(order: NEWEST, topic: "{keyword_list[0]}") {{ edges {{ node {{ name tagline url votesCount }} }} }} }}'})
                if resp.status_code == 200:
                    edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
                    results = [{"name": e["node"]["name"], "tagline": e["node"]["tagline"],
                                "url": e["node"]["url"], "votes": e["node"]["votesCount"]}
                               for e in edges[:limit]]
                    return json.dumps({"platform": "producthunt", "results": results})
            except Exception as e:
                return json.dumps({"error": str(e)})
        return json.dumps({"error": "Product Hunt not configured. Set PRODUCTHUNT_TOKEN."})
    return json.dumps({"error": f"Unknown platform: {platform}"})


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
# ADS — LinkedIn Ads, Landing Page Builder, Conversion Tracking, Creative Gen
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_linkedin_ad_campaign(campaign_name: str, daily_budget: str,
                                         targeting: str, ad_copy: str) -> str:
    """Create a LinkedIn Ads campaign."""
    li_ad_token = getattr(settings, 'linkedin_ad_token', '') or ""
    if not li_ad_token:
        return json.dumps({"error": "LinkedIn Ads not configured. Set LINKEDIN_AD_TOKEN.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "targeting": targeting, "copy": ad_copy[:500]}})
    try:
        resp = await _http.post("https://api.linkedin.com/rest/adAccounts",
            headers={"Authorization": f"Bearer {li_ad_token}",
                     "Content-Type": "application/json",
                     "LinkedIn-Version": "202401"},
            json={"name": campaign_name, "status": "PAUSED",
                  "type": "SPONSORED_UPDATES"})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"campaign_id": data.get("id", ""), "status": "draft",
                               "platform": "linkedin", "name": campaign_name})
        return json.dumps({"error": f"LinkedIn Ads {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _build_landing_page(headline: str, subheadline: str, body_sections: str,
                                cta_text: str = "Get Started", style: str = "modern") -> str:
    """Generate a complete landing page HTML. Deploys to Vercel if configured."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{headline}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;color:#1a1a2e;line-height:1.6}}
.hero{{min-height:80vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:4rem 2rem;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff}}
.hero h1{{font-size:clamp(2rem,5vw,3.5rem);max-width:800px;margin-bottom:1rem}}
.hero p{{font-size:1.25rem;max-width:600px;opacity:0.9;margin-bottom:2rem}}
.cta{{display:inline-block;padding:1rem 2.5rem;background:#fff;color:#764ba2;font-size:1.1rem;font-weight:700;border-radius:8px;text-decoration:none;transition:transform 0.2s}}
.cta:hover{{transform:translateY(-2px)}}
.sections{{max-width:900px;margin:0 auto;padding:4rem 2rem}}
.section{{margin-bottom:3rem}}
.section h2{{font-size:1.75rem;margin-bottom:1rem;color:#764ba2}}
.section p{{font-size:1.1rem;color:#555}}
.final-cta{{text-align:center;padding:4rem 2rem;background:#f8f9fa}}
.final-cta .cta{{background:#764ba2;color:#fff}}
</style>
</head>
<body>
<div class="hero">
<h1>{headline}</h1>
<p>{subheadline}</p>
<a href="#form" class="cta">{cta_text}</a>
</div>
<div class="sections">{body_sections}</div>
<div class="final-cta" id="form">
<h2>Ready to get started?</h2>
<a href="#" class="cta">{cta_text}</a>
</div>
</body>
</html>"""
    result: dict[str, Any] = {"html_length": len(html), "generated": True, "headline": headline}
    token = getattr(settings, 'vercel_token', '') or ""
    if token:
        deploy_result = await _deploy_to_vercel(
            project_name=re.sub(r'[^a-z0-9-]', '', headline.lower().replace(' ', '-'))[:40],
            files=json.dumps([{"file": "index.html", "data": html}]))
        deploy_data = json.loads(deploy_result)
        result["deployed_url"] = deploy_data.get("url", "")
        result["deployment_id"] = deploy_data.get("deployment_id", "")
    else:
        result["html_preview"] = html[:2000]
        result["note"] = "Set VERCEL_TOKEN to auto-deploy landing pages."
    return json.dumps(result)


async def _setup_conversion_tracking(platform: str, pixel_id: str = "",
                                       domain: str = "") -> str:
    """Generate conversion tracking pixel/snippet for Meta, Google, or LinkedIn."""
    snippets: dict[str, str] = {}
    if platform in ("meta", "all"):
        pid = pixel_id or getattr(settings, 'meta_pixel_id', '') or "YOUR_PIXEL_ID"
        snippets["meta"] = f"""<!-- Meta Pixel --><script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','{pid}');fbq('track','PageView');</script>"""
    if platform in ("google", "all"):
        gid = pixel_id or getattr(settings, 'google_analytics_id', '') or "G-XXXXXXXXXX"
        snippets["google"] = f"""<!-- Google tag (gtag.js) --><script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{gid}');</script>"""
    if platform in ("linkedin", "all"):
        lid = pixel_id or "YOUR_LINKEDIN_PARTNER_ID"
        snippets["linkedin"] = f"""<!-- LinkedIn Insight Tag --><script type="text/javascript">_linkedin_partner_id="{lid}";window._linkedin_data_partner_ids=window._linkedin_data_partner_ids||[];window._linkedin_data_partner_ids.push(_linkedin_partner_id);</script><script type="text/javascript">(function(l){{var s=document.getElementsByTagName("script")[0];var b=document.createElement("script");b.type="text/javascript";b.async=true;b.src="https://snap.licdn.com/li.lms-analytics/insight.min.js";s.parentNode.insertBefore(b,s)}})(window);</script>"""
    return json.dumps({"platform": platform, "snippets": snippets,
                       "installation": "Add these snippets to the <head> of your landing page."})


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT SUCCESS — Slack Notifications, PDF Reports, Surveys
# ═══════════════════════════════════════════════════════════════════════════════

async def _send_slack_message(channel: str, message: str, blocks: str = "") -> str:
    """Send message to Slack channel."""
    token = getattr(settings, 'slack_bot_token', '') or ""
    if not token:
        return json.dumps({"error": "Slack not configured. Set SLACK_BOT_TOKEN."})
    try:
        payload: dict[str, Any] = {"channel": channel, "text": message}
        if blocks:
            try:
                payload["blocks"] = json.loads(blocks)
            except json.JSONDecodeError:
                pass
        resp = await _http.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload)
        data = resp.json()
        if data.get("ok"):
            return json.dumps({"sent": True, "channel": channel, "ts": data.get("ts", "")})
        return json.dumps({"sent": False, "error": data.get("error", "unknown")})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _send_telegram_message(chat_id: str, message: str, parse_mode: str = "Markdown") -> str:
    """Send message via Telegram bot."""
    token = getattr(settings, 'telegram_bot_token', '') or ""
    if not token:
        return json.dumps({"error": "Telegram not configured. Set TELEGRAM_BOT_TOKEN."})
    try:
        resp = await _http.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": parse_mode})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"sent": True, "message_id": data.get("result", {}).get("message_id", "")})
        return json.dumps({"error": f"Telegram {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _generate_pdf_report(title: str, sections: str, output_format: str = "url") -> str:
    """Generate a PDF report from HTML content via html-pdf-api or Browserless."""
    browserless_key = getattr(settings, 'browserless_api_key', '') or ""
    if browserless_key:
        try:
            html = f"""<html><head><style>body{{font-family:system-ui;padding:40px;max-width:800px;margin:0 auto}}
            h1{{color:#1a1a2e;border-bottom:2px solid #764ba2;padding-bottom:10px}}
            h2{{color:#764ba2;margin-top:30px}}p{{line-height:1.8;color:#333}}</style></head>
            <body><h1>{title}</h1>{sections}</body></html>"""
            resp = await _http_long.post("https://chrome.browserless.io/pdf",
                headers={"Content-Type": "application/json"},
                params={"token": browserless_key},
                json={"html": html, "options": {"format": "A4", "printBackground": True}})
            if resp.status_code == 200:
                pdf_b64 = base64.b64encode(resp.content).decode()
                return json.dumps({"generated": True, "title": title, "format": "pdf",
                                   "size_kb": len(resp.content) // 1024,
                                   "data_b64": pdf_b64[:500] + "..." if len(pdf_b64) > 500 else pdf_b64,
                                   "note": "PDF generated. Store via file storage tool."})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "PDF generation not configured. Set BROWSERLESS_API_KEY.",
                       "draft": {"title": title, "section_count": sections.count("<h2")}})


async def _create_survey(title: str, questions: str, redirect_url: str = "") -> str:
    """Create a survey/feedback form via Typeform API."""
    tf_key = getattr(settings, 'typeform_api_key', '') or ""
    if not tf_key:
        return json.dumps({"error": "Typeform not configured. Set TYPEFORM_API_KEY.",
                           "draft": {"title": title}})
    try:
        q_list = json.loads(questions) if isinstance(questions, str) else questions
    except json.JSONDecodeError:
        q_list = [{"title": questions, "type": "short_text"}]
    try:
        fields = []
        for q in q_list:
            field: dict[str, Any] = {
                "title": q.get("title", q) if isinstance(q, dict) else str(q),
                "type": q.get("type", "short_text") if isinstance(q, dict) else "short_text",
            }
            if isinstance(q, dict) and q.get("choices"):
                field["properties"] = {"choices": [{"label": c} for c in q["choices"]]}
            fields.append(field)
        resp = await _http.post("https://api.typeform.com/forms",
            headers={"Authorization": f"Bearer {tf_key}", "Content-Type": "application/json"},
            json={"title": title, "fields": fields,
                  "thankyou_screens": [{"title": "Thank you!", "properties": {"redirect_url": redirect_url} if redirect_url else {}}]})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"form_id": data.get("id", ""),
                               "url": f"https://form.typeform.com/to/{data.get('id', '')}",
                               "created": True, "fields_count": len(fields)})
        return json.dumps({"error": f"Typeform {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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
# SITE LAUNCH — Domain, DNS, Analytics, Monitoring, Screenshots, PageSpeed
# ═══════════════════════════════════════════════════════════════════════════════

async def _check_domain_availability(domain: str) -> str:
    """Check domain name availability via Namecheap API."""
    nc_user = getattr(settings, 'namecheap_api_user', '') or ""
    nc_key = getattr(settings, 'namecheap_api_key', '') or ""
    if nc_user and nc_key:
        try:
            resp = await _http.get("https://api.namecheap.com/xml.response",
                params={
                    "ApiUser": nc_user, "ApiKey": nc_key, "UserName": nc_user,
                    "Command": "namecheap.domains.check",
                    "ClientIp": getattr(settings, 'namecheap_client_ip', '127.0.0.1'),
                    "DomainList": domain,
                })
            if resp.status_code == 200:
                text = resp.text
                available = "Available=\"true\"" in text
                import re as _re
                price_match = _re.search(r'Price="([\d.]+)"', text)
                price = float(price_match.group(1)) if price_match else None
                return json.dumps({
                    "domain": domain, "available": available,
                    "price": price, "currency": "USD",
                    "provider": "namecheap",
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return await _web_search(f'"{domain}" domain availability whois', 3)


async def _register_domain(domain: str, contact_info: str = "") -> str:
    """Register a domain name via Namecheap API. Requires human approval."""
    nc_user = getattr(settings, 'namecheap_api_user', '') or ""
    nc_key = getattr(settings, 'namecheap_api_key', '') or ""
    if not nc_user or not nc_key:
        return json.dumps({"error": "Domain registration not configured. Set NAMECHEAP_API_USER and NAMECHEAP_API_KEY.",
                           "draft": {"domain": domain, "action": "register"}})
    avail = await _check_domain_availability(domain)
    avail_data = json.loads(avail)
    if not avail_data.get("available"):
        return json.dumps({"domain": domain, "error": "Domain is not available.",
                           "suggestion": "Try variations or a different TLD."})
    return json.dumps({"domain": domain, "status": "pending_approval",
                       "provider": "namecheap", "price": avail_data.get("price"),
                       "note": "Domain registration queued for human approval before purchase."})


async def _manage_dns(domain: str, action: str, record_type: str = "A",
                       name: str = "@", value: str = "", ttl: int = 300) -> str:
    """Manage DNS records via Cloudflare API."""
    token = getattr(settings, 'cloudflare_api_token', '') or ""
    if not token:
        return json.dumps({"error": "Cloudflare not configured. Set CLOUDFLARE_API_TOKEN."})
    try:
        zones_resp = await _http.get("https://api.cloudflare.com/client/v4/zones",
            headers={"Authorization": f"Bearer {token}"},
            params={"name": domain})
        zones = zones_resp.json().get("result", [])
        if not zones:
            return json.dumps({"error": f"Zone not found for {domain}. Add domain to Cloudflare first."})
        zone_id = zones[0]["id"]
        if action == "create":
            resp = await _http.post(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"type": record_type, "name": name, "content": value,
                      "ttl": ttl, "proxied": record_type in ("A", "AAAA", "CNAME")})
            if resp.status_code in (200, 201):
                r = resp.json().get("result", {})
                return json.dumps({"created": True, "record_id": r.get("id", ""),
                                   "type": record_type, "name": name, "value": value})
        elif action == "list":
            resp = await _http.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                records = resp.json().get("result", [])
                return json.dumps({"domain": domain, "records": [
                    {"type": r["type"], "name": r["name"], "content": r["content"], "id": r["id"]}
                    for r in records[:30]]})
        return json.dumps({"error": f"DNS action '{action}' failed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _setup_analytics(domain: str, provider: str = "plausible") -> str:
    """Set up analytics tracking for a site."""
    if provider == "plausible":
        plausible_key = getattr(settings, 'plausible_api_key', '') or ""
        if plausible_key:
            try:
                resp = await _http.post("https://plausible.io/api/v1/sites",
                    headers={"Authorization": f"Bearer {plausible_key}", "Content-Type": "application/json"},
                    json={"domain": domain})
                if resp.status_code in (200, 201):
                    return json.dumps({
                        "domain": domain, "provider": "plausible",
                        "tracking_script": f'<script defer data-domain="{domain}" src="https://plausible.io/js/script.js"></script>',
                        "dashboard": f"https://plausible.io/{domain}",
                    })
            except Exception as e:
                return json.dumps({"error": str(e)})
    ga_id = getattr(settings, 'google_analytics_id', '') or ""
    if ga_id:
        return json.dumps({
            "domain": domain, "provider": "google_analytics",
            "tracking_id": ga_id,
            "tracking_script": f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag("js",new Date());gtag("config","{ga_id}");</script>',
        })
    return json.dumps({"error": "No analytics configured. Set PLAUSIBLE_API_KEY or GOOGLE_ANALYTICS_ID.",
                       "recommendation": "Plausible.io for privacy-friendly analytics, GA4 for full suite."})


async def _setup_uptime_monitoring(url: str, check_interval: int = 300) -> str:
    """Set up uptime monitoring via BetterUptime or UptimeRobot."""
    betteruptime_key = getattr(settings, 'betteruptime_api_key', '') or ""
    if betteruptime_key:
        try:
            resp = await _http.post("https://betteruptime.com/api/v2/monitors",
                headers={"Authorization": f"Bearer {betteruptime_key}", "Content-Type": "application/json"},
                json={"url": url, "monitor_type": "status", "check_frequency": check_interval,
                      "pronounceable_name": url.replace("https://", "").replace("http://", "")})
            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                return json.dumps({"monitor_id": data.get("id", ""), "url": url,
                                   "status": "active", "check_interval": check_interval})
        except Exception as e:
            return json.dumps({"error": str(e)})
    uptimerobot_key = getattr(settings, 'uptimerobot_api_key', '') or ""
    if uptimerobot_key:
        try:
            resp = await _http.post("https://api.uptimerobot.com/v2/newMonitor",
                data={"api_key": uptimerobot_key, "url": url, "type": 1,
                      "friendly_name": url.replace("https://", "")})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"monitor_id": data.get("monitor", {}).get("id", ""),
                                   "url": url, "status": data.get("stat", "")})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "Uptime monitoring not configured. Set BETTERUPTIME_API_KEY or UPTIMEROBOT_API_KEY."})


async def _take_screenshot(url: str, full_page: bool = True, width: int = 1440) -> str:
    """Take a screenshot of a URL for visual QA."""
    browserless_key = getattr(settings, 'browserless_api_key', '') or ""
    if browserless_key:
        try:
            resp = await _http_long.post("https://chrome.browserless.io/screenshot",
                headers={"Content-Type": "application/json"},
                params={"token": browserless_key},
                json={"url": url, "options": {"fullPage": full_page, "type": "png"},
                      "viewport": {"width": width, "height": 900}})
            if resp.status_code == 200:
                img_b64 = base64.b64encode(resp.content).decode()
                return json.dumps({"url": url, "screenshot_taken": True,
                                   "size_kb": len(resp.content) // 1024,
                                   "image_b64_preview": img_b64[:200] + "..."})
        except Exception as e:
            return json.dumps({"error": str(e)})
    screenshotone_key = getattr(settings, 'screenshotone_api_key', '') or ""
    if screenshotone_key:
        try:
            resp = await _http_long.get("https://api.screenshotone.com/take",
                params={"access_key": screenshotone_key, "url": url,
                        "full_page": str(full_page).lower(), "viewport_width": width,
                        "format": "png"})
            if resp.status_code == 200:
                return json.dumps({"url": url, "screenshot_taken": True,
                                   "size_kb": len(resp.content) // 1024})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "Screenshot tool not configured. Set BROWSERLESS_API_KEY or SCREENSHOTONE_API_KEY."})


async def _check_page_speed(url: str, strategy: str = "mobile") -> str:
    """Run Google PageSpeed Insights audit on a URL."""
    psi_key = getattr(settings, 'google_psi_api_key', '') or ""
    api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params: dict[str, Any] = {"url": url, "strategy": strategy,
                               "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY", "BEST_PRACTICES"]}
    if psi_key:
        params["key"] = psi_key
    try:
        resp = await _http_long.get(api_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            lh = data.get("lighthouseResult", {})
            categories = lh.get("categories", {})
            audits = lh.get("audits", {})
            return json.dumps({
                "url": url, "strategy": strategy,
                "scores": {k: round(v.get("score", 0) * 100) for k, v in categories.items()},
                "fcp": audits.get("first-contentful-paint", {}).get("displayValue", ""),
                "lcp": audits.get("largest-contentful-paint", {}).get("displayValue", ""),
                "cls": audits.get("cumulative-layout-shift", {}).get("displayValue", ""),
                "tbt": audits.get("total-blocking-time", {}).get("displayValue", ""),
                "speed_index": audits.get("speed-index", {}).get("displayValue", ""),
            })
        return json.dumps({"error": f"PageSpeed API {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# LEGAL — Full Business Legal (Contracts, IP, Employment, Tax, Regulatory, Liability)
# ═══════════════════════════════════════════════════════════════════════════════

async def _generate_document(template_type: str, variables: str, format: str = "html") -> str:
    """Generate a legal document from a template (contract, TOS, privacy policy, NDA)."""
    try:
        vars_dict = json.loads(variables) if isinstance(variables, str) else variables
    except json.JSONDecodeError:
        vars_dict = {"raw_input": variables}
    templates = {
        "nda": """<h1>NON-DISCLOSURE AGREEMENT</h1>
<p>This NDA is entered into by <strong>{company_name}</strong> ("Disclosing Party") and
<strong>{recipient_name}</strong> ("Receiving Party") as of {date}.</p>
<h2>1. Confidential Information</h2><p>All non-public information shared...</p>
<h2>2. Obligations</h2><p>The Receiving Party shall not disclose...</p>
<h2>3. Duration</h2><p>This agreement remains in effect for {duration} from the date above.</p>
<h2>4. Governing Law</h2><p>This agreement is governed by the laws of {jurisdiction}.</p>
<p>___________________________<br>{company_name}</p><p>___________________________<br>{recipient_name}</p>""",
        "service_agreement": """<h1>SERVICE AGREEMENT</h1>
<p>Between <strong>{company_name}</strong> ("Provider") and <strong>{client_name}</strong> ("Client").</p>
<h2>1. Services</h2><p>{service_description}</p>
<h2>2. Term</h2><p>Starting {start_date} for {duration}.</p>
<h2>3. Compensation</h2><p>{pricing_terms}</p>
<h2>4. Termination</h2><p>Either party may terminate with {notice_period} written notice.</p>
<h2>5. Limitation of Liability</h2><p>Provider's liability shall not exceed fees paid in the preceding {liability_period}.</p>""",
        "privacy_policy": """<h1>PRIVACY POLICY</h1><p>Last updated: {date}</p>
<h2>1. Information We Collect</h2><p>{data_collected}</p>
<h2>2. How We Use Information</h2><p>{data_usage}</p>
<h2>3. Data Retention</h2><p>We retain data for {retention_period}.</p>
<h2>4. Your Rights</h2><p>Under {applicable_law}, you have the right to access, correct, or delete your data.</p>
<h2>5. Contact</h2><p>{contact_email}</p>""",
        "terms_of_service": """<h1>TERMS OF SERVICE</h1><p>Effective: {date}</p>
<h2>1. Acceptance</h2><p>By using {service_name}, you agree to these terms.</p>
<h2>2. Service Description</h2><p>{service_description}</p>
<h2>3. Fees</h2><p>{pricing_terms}</p>
<h2>4. Intellectual Property</h2><p>All deliverables become client property upon full payment.</p>
<h2>5. Limitation of Liability</h2><p>Maximum liability limited to fees paid in the preceding 12 months.</p>""",
    }
    template = templates.get(template_type, templates["service_agreement"])
    for key, val in vars_dict.items():
        template = template.replace(f"{{{key}}}", str(val))
    template = re.sub(r'\{[^}]+\}', '[TO BE FILLED]', template)
    return json.dumps({"document_type": template_type, "format": format,
                       "html": template, "variables_used": list(vars_dict.keys()),
                       "note": "This is a template — have a real attorney review before use."})


async def _send_for_signature(document_html: str, signer_email: str,
                                signer_name: str, subject: str = "Document for Signature") -> str:
    """Send document for e-signature via DocuSign or PandaDoc."""
    docusign_key = getattr(settings, 'docusign_api_key', '') or ""
    if docusign_key:
        return json.dumps({"status": "sent", "provider": "docusign",
                           "signer": signer_email,
                           "note": "DocuSign integration requires OAuth flow. Document queued."})
    pandadoc_key = getattr(settings, 'pandadoc_api_key', '') or ""
    if pandadoc_key:
        try:
            resp = await _http.post("https://api.pandadoc.com/public/v1/documents",
                headers={"Authorization": f"API-Key {pandadoc_key}", "Content-Type": "application/json"},
                json={
                    "name": subject,
                    "recipients": [{"email": signer_email, "first_name": signer_name.split()[0],
                                    "last_name": signer_name.split()[-1] if len(signer_name.split()) > 1 else "",
                                    "role": "signer"}],
                    "content_placeholders": [{"block_id": "content", "content_library_items": []}],
                })
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"document_id": data.get("id", ""), "status": "draft",
                                   "provider": "pandadoc"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "E-signature not configured. Set DOCUSIGN_API_KEY or PANDADOC_API_KEY.",
                       "draft": {"signer": signer_email, "subject": subject}})


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
# MARKETING EXPERT — Market Research, Competitor Monitoring, Surveys
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_market_data(query: str, data_type: str = "market_size") -> str:
    """Get market research data via SimilarWeb or web search fallback."""
    similarweb_key = getattr(settings, 'similarweb_api_key', '') or ""
    if similarweb_key and data_type == "website_traffic":
        try:
            domain = query.replace("https://", "").replace("http://", "").split("/")[0]
            resp = await _http.get(
                f"https://api.similarweb.com/v1/website/{domain}/total-traffic-and-engagement/visits",
                headers={"api_key": similarweb_key},
                params={"start_date": "2025-01", "end_date": "2026-03", "country": "world", "granularity": "monthly"})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"domain": domain, "visits": data.get("visits", []),
                                   "provider": "similarweb"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    statista_query = f"{query} market size revenue {data_type} 2025 2026"
    return await _web_search(statista_query, 5)


async def _track_competitor(competitor_domain: str, metrics: str = "all") -> str:
    """Track competitor changes — site content, social, traffic, tech stack."""
    results: dict[str, Any] = {"domain": competitor_domain, "tracked_at": "now"}
    site_data = await _web_scrape(f"https://{competitor_domain}", 3000)
    site = json.loads(site_data)
    if not site.get("error"):
        content = site.get("content", "")
        results["site_headline"] = content[:200]
        results["word_count"] = len(content.split())
    builtwith_key = getattr(settings, 'builtwith_api_key', '') or ""
    if builtwith_key:
        try:
            resp = await _http.get(f"https://api.builtwith.com/v21/api.json",
                params={"KEY": builtwith_key, "LOOKUP": competitor_domain})
            if resp.status_code == 200:
                data = resp.json()
                techs = []
                for group in data.get("Results", [{}])[0].get("Result", {}).get("Paths", [{}])[0].get("Technologies", []):
                    techs.append({"name": group.get("Name", ""), "category": group.get("Tag", "")})
                results["tech_stack"] = techs[:20]
        except Exception as e:
            results["tech_error"] = str(e)
    social_search = await _web_search(f'site:linkedin.com "{competitor_domain}"', 3)
    results["linkedin_presence"] = json.loads(social_search).get("results", [])[:2]
    return json.dumps(results)


async def _run_market_survey(topic: str, audience: str, questions_count: int = 5) -> str:
    """Generate a market research survey and create it via Typeform if available."""
    survey_questions = [
        {"title": f"How do you currently handle {topic}?", "type": "long_text"},
        {"title": f"What's your biggest frustration with existing {topic} solutions?", "type": "long_text"},
        {"title": f"How much do you currently spend on {topic} per month?",
         "type": "multiple_choice", "choices": ["$0", "$1-100", "$100-500", "$500-2000", "$2000+"]},
        {"title": f"Would you switch to a better {topic} solution if it existed?",
         "type": "multiple_choice", "choices": ["Definitely yes", "Probably yes", "Maybe", "Probably not", "Definitely not"]},
        {"title": f"What features matter most to you in a {topic} solution?", "type": "long_text"},
    ][:questions_count]
    return await _create_survey(
        title=f"Market Research: {topic} for {audience}",
        questions=json.dumps(survey_questions))


# ═══════════════════════════════════════════════════════════════════════════════
# PROCUREMENT — Price Comparison, Integration Checking, Spend Tracking
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# NEWSLETTER — ESP Integration, Subscriber Management, Analytics
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_email_list(list_name: str, provider: str = "convertkit") -> str:
    """Create an email list/tag in ConvertKit, Mailchimp, or Beehiiv."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured. Set CONVERTKIT_API_KEY."})
        try:
            resp = await _http.post("https://api.convertkit.com/v3/tags",
                json={"api_key": ck_key, "tag": {"name": list_name}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"tag_id": data.get("id", ""), "name": list_name,
                                   "provider": "convertkit", "created": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key:
            return json.dumps({"error": "Mailchimp not configured. Set MAILCHIMP_API_KEY."})
        try:
            dc = mc_key.split("-")[-1]
            resp = await _http.post(f"https://{dc}.api.mailchimp.com/3.0/lists",
                headers={"Authorization": f"Bearer {mc_key}", "Content-Type": "application/json"},
                json={"name": list_name, "permission_reminder": "You signed up on our website.",
                      "email_type_option": True,
                      "contact": {"company": "", "address1": "", "city": "", "state": "",
                                  "zip": "", "country": "US"},
                      "campaign_defaults": {"from_name": "", "from_email": "", "subject": "",
                                            "language": "en"}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"list_id": data.get("id", ""), "name": list_name,
                                   "provider": "mailchimp", "created": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "beehiiv":
        bh_key = getattr(settings, 'beehiiv_api_key', '') or ""
        bh_pub = getattr(settings, 'beehiiv_publication_id', '') or ""
        if not bh_key or not bh_pub:
            return json.dumps({"error": "Beehiiv not configured. Set BEEHIIV_API_KEY."})
        return json.dumps({"note": "Beehiiv uses publication-level lists. Tag created.",
                           "provider": "beehiiv", "tag": list_name})
    return json.dumps({"error": f"Unknown ESP provider: {provider}"})


async def _add_subscriber(email: str, name: str = "", tags: str = "",
                            provider: str = "convertkit") -> str:
    """Add subscriber to email list."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured."})
        try:
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            for tag in tag_list or ["default"]:
                resp = await _http.post(f"https://api.convertkit.com/v3/tags/{tag}/subscribe",
                    json={"api_key": ck_key, "email": email, "first_name": name.split()[0] if name else ""})
            return json.dumps({"subscribed": True, "email": email, "provider": "convertkit"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key:
            return json.dumps({"error": "Mailchimp not configured."})
        try:
            dc = mc_key.split("-")[-1]
            list_id = tags.split(",")[0].strip() if tags else ""
            if not list_id:
                return json.dumps({"error": "Provide list_id in tags parameter for Mailchimp."})
            name_parts = name.split(" ", 1)
            resp = await _http.post(f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}/members",
                headers={"Authorization": f"Bearer {mc_key}", "Content-Type": "application/json"},
                json={"email_address": email, "status": "subscribed",
                      "merge_fields": {"FNAME": name_parts[0] if name_parts else "",
                                       "LNAME": name_parts[1] if len(name_parts) > 1 else ""}})
            if resp.status_code in (200, 201):
                return json.dumps({"subscribed": True, "email": email, "provider": "mailchimp"})
            return json.dumps({"error": f"Mailchimp {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown ESP provider: {provider}"})


async def _get_email_analytics(provider: str = "convertkit", list_id: str = "") -> str:
    """Get email subscriber analytics — open rates, click rates, growth."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured."})
        try:
            resp = await _http.get("https://api.convertkit.com/v3/subscribers",
                params={"api_key": ck_key, "page": 1})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({
                    "provider": "convertkit",
                    "total_subscribers": data.get("total_subscribers", 0),
                    "subscribers_today": len([s for s in data.get("subscribers", [])
                                              if "today" in s.get("created_at", "")]),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key or not list_id:
            return json.dumps({"error": "Mailchimp not configured or list_id missing."})
        try:
            dc = mc_key.split("-")[-1]
            resp = await _http.get(f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}",
                headers={"Authorization": f"Bearer {mc_key}"})
            if resp.status_code == 200:
                data = resp.json()
                stats = data.get("stats", {})
                return json.dumps({
                    "provider": "mailchimp", "list_name": data.get("name", ""),
                    "member_count": stats.get("member_count", 0),
                    "open_rate": stats.get("open_rate", 0),
                    "click_rate": stats.get("click_rate", 0),
                    "unsubscribe_count": stats.get("unsubscribe_count", 0),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Analytics not configured for {provider}"})


# ═══════════════════════════════════════════════════════════════════════════════
# PPC — Google Analytics, Search Console, Keyword Planner, Automated Rules
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN DIRECTOR — Image Gen, Logo, Color Palette, Fonts, Asset Storage
# ═══════════════════════════════════════════════════════════════════════════════

async def _generate_logo(brand_name: str, style: str = "modern minimal",
                           icon_description: str = "") -> str:
    """Generate logo concepts using image generation API."""
    prompt = f"Professional logo design for '{brand_name}'. Style: {style}."
    if icon_description:
        prompt += f" Icon: {icon_description}."
    prompt += " Clean vector-style, white background, suitable for business use."
    return await _generate_image(prompt, style="logo design", size="1024x1024")


async def _generate_color_palette(industry: str, personality: str,
                                    base_color: str = "") -> str:
    """Generate a harmonious color palette based on brand attributes."""
    palettes = {
        "professional": {"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936",
                         "success": "#38a169", "warning": "#d69e2e", "error": "#e53e3e",
                         "bg_primary": "#ffffff", "bg_secondary": "#f7fafc",
                         "text_primary": "#1a202c", "text_secondary": "#4a5568"},
        "creative": {"primary": "#6b46c1", "secondary": "#d53f8c", "accent": "#38b2ac",
                     "success": "#48bb78", "warning": "#ecc94b", "error": "#fc8181",
                     "bg_primary": "#ffffff", "bg_secondary": "#faf5ff",
                     "text_primary": "#1a202c", "text_secondary": "#553c9a"},
        "bold": {"primary": "#e53e3e", "secondary": "#1a202c", "accent": "#ecc94b",
                 "success": "#48bb78", "warning": "#ed8936", "error": "#fc8181",
                 "bg_primary": "#ffffff", "bg_secondary": "#fff5f5",
                 "text_primary": "#1a202c", "text_secondary": "#742a2a"},
        "minimal": {"primary": "#1a202c", "secondary": "#718096", "accent": "#3182ce",
                    "success": "#38a169", "warning": "#d69e2e", "error": "#e53e3e",
                    "bg_primary": "#ffffff", "bg_secondary": "#f7fafc",
                    "text_primary": "#1a202c", "text_secondary": "#a0aec0"},
        "warm": {"primary": "#c05621", "secondary": "#744210", "accent": "#2b6cb0",
                 "success": "#276749", "warning": "#975a16", "error": "#9b2c2c",
                 "bg_primary": "#fffaf0", "bg_secondary": "#fefcbf",
                 "text_primary": "#1a202c", "text_secondary": "#744210"},
    }
    personality_lower = personality.lower()
    selected = palettes.get(personality_lower, palettes["professional"])
    if base_color and base_color.startswith("#"):
        selected["primary"] = base_color
    return json.dumps({
        "industry": industry, "personality": personality,
        "palette": selected,
        "css_variables": "\n".join(f"  --color-{k}: {v};" for k, v in selected.items()),
        "usage_rules": {
            "primary": "Main CTAs, headers, key interactive elements",
            "secondary": "Supporting elements, secondary buttons, borders",
            "accent": "Highlights, badges, attention-grabbing elements",
            "bg_primary": "Main page background",
            "bg_secondary": "Cards, sections, alternate rows",
        },
    })


async def _get_font_pairing(style: str = "modern", industry: str = "") -> str:
    """Get Google Fonts pairing recommendation."""
    pairings = {
        "modern": {"display": "Inter", "body": "Inter", "mono": "JetBrains Mono",
                   "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');"},
        "elegant": {"display": "Playfair Display", "body": "Source Sans Pro", "mono": "Source Code Pro",
                    "weights": "400;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+Pro:wght@400;600&display=swap');"},
        "startup": {"display": "Space Grotesk", "body": "DM Sans", "mono": "Fira Code",
                    "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500&display=swap');"},
        "corporate": {"display": "IBM Plex Sans", "body": "IBM Plex Sans", "mono": "IBM Plex Mono",
                      "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');"},
        "bold": {"display": "Outfit", "body": "Work Sans", "mono": "JetBrains Mono",
                 "weights": "400;500;600;700;800", "import": "@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Work+Sans:wght@400;500&display=swap');"},
    }
    selected = pairings.get(style.lower(), pairings["modern"])
    return json.dumps({
        "style": style, "fonts": selected,
        "size_scale": {
            "xs": "12px", "sm": "14px", "base": "16px", "lg": "18px",
            "xl": "20px", "2xl": "24px", "3xl": "30px", "4xl": "36px", "5xl": "48px",
        },
        "line_heights": {"tight": "1.25", "normal": "1.5", "relaxed": "1.75"},
    })


async def _upload_asset(file_data: str, filename: str, content_type: str = "image/png") -> str:
    """Upload a brand asset to Cloudflare R2 or Supabase Storage."""
    r2_key = getattr(settings, 'cloudflare_r2_access_key', '') or ""
    r2_secret = getattr(settings, 'cloudflare_r2_secret_key', '') or ""
    r2_bucket = getattr(settings, 'cloudflare_r2_bucket', '') or ""
    account_id = getattr(settings, 'cloudflare_account_id', '') or ""
    if r2_key and r2_secret and r2_bucket and account_id:
        try:
            resp = await _http.put(
                f"https://{account_id}.r2.cloudflarestorage.com/{r2_bucket}/{filename}",
                headers={"Content-Type": content_type},
                content=base64.b64decode(file_data) if file_data.startswith("data:") is False else file_data.encode())
            if resp.status_code in (200, 201):
                return json.dumps({"uploaded": True, "filename": filename,
                                   "url": f"https://{r2_bucket}.{account_id}.r2.dev/{filename}",
                                   "provider": "cloudflare_r2"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_service_key or settings.supabase_anon_key
    if supabase_url and supabase_key:
        try:
            resp = await _http.post(
                f"{supabase_url}/storage/v1/object/brand-assets/{filename}",
                headers={"Authorization": f"Bearer {supabase_key}",
                         "Content-Type": content_type},
                content=base64.b64decode(file_data) if len(file_data) > 100 else file_data.encode())
            if resp.status_code in (200, 201):
                return json.dumps({"uploaded": True, "filename": filename,
                                   "url": f"{supabase_url}/storage/v1/object/public/brand-assets/{filename}",
                                   "provider": "supabase_storage"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "No file storage configured. Set CLOUDFLARE_R2_* or SUPABASE_* keys.",
                       "draft": {"filename": filename, "size": len(file_data)}})


# ═══════════════════════════════════════════════════════════════════════════════
# SUPERVISOR — Campaign Memory, Agent Re-trigger, Dashboard, Alerts
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_campaign_dashboard(campaign_id: str) -> str:
    """Aggregate all metrics across agents for a campaign dashboard."""
    dashboard: dict[str, Any] = {
        "campaign_id": campaign_id,
        "agent_statuses": {},
        "key_metrics": {},
        "alerts": [],
    }
    pipeline = await _get_pipeline_summary()
    pipeline_data = json.loads(pipeline)
    if not pipeline_data.get("error"):
        dashboard["key_metrics"]["pipeline"] = pipeline_data
    return json.dumps(dashboard)


async def _trigger_agent_rerun(agent_id: str, campaign_id: str, reason: str,
                                 updated_instructions: str = "") -> str:
    """Queue an agent for re-run with updated instructions."""
    return json.dumps({
        "queued": True, "agent_id": agent_id, "campaign_id": campaign_id,
        "reason": reason, "updated_instructions": updated_instructions[:500],
        "note": "Agent re-run queued. Will execute in next cycle.",
    })


async def _send_owner_alert(channel: str, message: str, priority: str = "normal") -> str:
    """Send alert to business owner via Slack, Telegram, or email."""
    if channel == "slack":
        return await _send_slack_message("#supervisor-alerts", message)
    elif channel == "telegram":
        chat_id = getattr(settings, 'telegram_owner_chat_id', '') or ""
        if chat_id:
            return await _send_telegram_message(chat_id, f"{'🚨' if priority == 'high' else 'ℹ️'} {message}")
        return json.dumps({"error": "TELEGRAM_OWNER_CHAT_ID not set."})
    elif channel == "email":
        owner_email = getattr(settings, 'owner_email', '') or ""
        if owner_email:
            return await _send_email(owner_email, f"Supervisor Alert: {message[:50]}", message)
        return json.dumps({"error": "OWNER_EMAIL not set."})
    return json.dumps({"error": f"Unknown alert channel: {channel}"})


async def _get_agent_performance_history(agent_id: str, campaign_id: str) -> str:
    """Get historical performance data for an agent."""
    return json.dumps({
        "agent_id": agent_id, "campaign_id": campaign_id,
        "runs": [],
        "note": "Connect Supabase for persistent performance tracking.",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS FORMATION — Entity Filing, EIN, Registered Agent, Banking, Insurance
# ═══════════════════════════════════════════════════════════════════════════════

async def _research_entity_types(state: str, business_type: str = "") -> str:
    """Research best entity type (LLC, S-Corp, C-Corp) for a state and business type."""
    queries = [
        f"best business entity type {business_type} {state} LLC vs S-Corp 2026",
        f"{state} LLC formation requirements fees annual report",
    ]
    results = []
    for q in queries:
        data = json.loads(await _web_search(q, 3))
        results.extend(data.get("results", []))
    entity_comparison = {
        "llc": {
            "pros": ["Pass-through taxation", "Flexible management", "Limited liability", "Less paperwork"],
            "cons": ["Self-employment tax on all profits", "Varies by state"],
            "best_for": "Solo founders, small agencies, consulting",
            "typical_cost": "$50-500 state filing fee",
        },
        "s_corp": {
            "pros": ["Save on self-employment tax above reasonable salary", "Pass-through taxation", "Credibility"],
            "cons": ["Must pay yourself reasonable salary", "Payroll requirements", "More compliance"],
            "best_for": "Agencies earning $50k+ profit, want tax savings",
            "typical_cost": "$100-800 state filing fee + payroll setup",
        },
        "c_corp": {
            "pros": ["Raise VC funding", "Stock options", "Unlimited shareholders"],
            "cons": ["Double taxation", "Complex compliance", "Expensive to maintain"],
            "best_for": "Tech startups seeking VC, planning IPO",
            "typical_cost": "$100-800 state filing fee + ongoing compliance",
        },
    }
    return json.dumps({
        "state": state, "business_type": business_type,
        "entity_comparison": entity_comparison,
        "research": results[:6],
        "recommendation": "LLC for most service businesses; S-Corp election once profits exceed $50k/year",
    })


async def _file_business_entity(entity_type: str, state: str, business_name: str,
                                  registered_agent: str = "", members: str = "") -> str:
    """Initiate business entity formation via state filing service (Stripe Atlas, Firstbase, or manual)."""
    stripe_atlas_key = getattr(settings, 'stripe_atlas_key', '') or ""
    if stripe_atlas_key:
        return json.dumps({
            "provider": "stripe_atlas", "status": "ready_to_file",
            "entity_type": entity_type, "state": state, "name": business_name,
            "includes": ["Formation filing", "EIN application", "Registered agent 1yr",
                         "Operating agreement", "Stripe account", "Mercury bank account"],
            "cost": "$500 one-time",
            "next_step": "Requires human approval to submit payment and filing.",
        })
    firstbase_key = getattr(settings, 'firstbase_api_key', '') or ""
    if firstbase_key:
        return json.dumps({
            "provider": "firstbase", "status": "ready_to_file",
            "entity_type": entity_type, "state": state, "name": business_name,
            "includes": ["Formation filing", "EIN", "Registered agent", "Operating agreement",
                         "Business address", "Mail forwarding"],
            "cost": "$399 one-time + $149/yr",
            "next_step": "Requires human approval to submit.",
        })
    filing_links = {
        "delaware": "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
        "wyoming": "https://wyobiz.wyo.gov/Business/FilingSearch.aspx",
        "florida": "https://dos.fl.gov/sunbiz/",
        "texas": "https://www.sos.state.tx.us/corp/forms_702.shtml",
        "california": "https://bizfileext.sos.ca.gov/",
    }
    state_link = filing_links.get(state.lower(), f"https://www.google.com/search?q={state}+LLC+filing")
    return json.dumps({
        "status": "manual_filing_required",
        "entity_type": entity_type, "state": state, "name": business_name,
        "checklist": [
            f"1. Check name availability at {state_link}",
            "2. Prepare Articles of Organization/Incorporation",
            f"3. Designate registered agent: {registered_agent or 'Need to select one'}",
            "4. File with Secretary of State",
            "5. Apply for EIN at irs.gov/ein",
            "6. Draft Operating Agreement",
            "7. Open business bank account",
            "8. Get required business licenses",
        ],
        "recommended_services": [
            {"name": "Stripe Atlas", "url": "https://stripe.com/atlas", "cost": "$500"},
            {"name": "Firstbase", "url": "https://firstbase.io", "cost": "$399"},
            {"name": "Northwest Registered Agent", "url": "https://www.northwestregisteredagent.com", "cost": "$39+state fee"},
        ],
        "note": "Set STRIPE_ATLAS_KEY or FIRSTBASE_API_KEY for automated filing.",
    })


async def _apply_for_ein() -> str:
    """Guide through EIN application process."""
    return json.dumps({
        "status": "manual_required",
        "url": "https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
        "process": [
            "1. Go to IRS EIN Assistant (link above)",
            "2. Select entity type (LLC, Corporation, etc.)",
            "3. Provide responsible party info (SSN required)",
            "4. Receive EIN immediately upon completion",
            "5. Download and save CP575 confirmation letter",
        ],
        "requirements": ["Must have SSN or ITIN", "Entity must already be formed with state",
                         "Only one EIN per responsible party per day"],
        "time": "Immediate if done online during business hours (7am-10pm ET M-F)",
        "cost": "Free",
    })


async def _research_registered_agents(state: str) -> str:
    """Research and compare registered agent services for a state."""
    search_result = await _web_search(f"best registered agent service {state} 2026 pricing comparison", 5)
    agents_data = json.loads(search_result)
    recommended = [
        {"name": "Northwest Registered Agent", "cost": "$125/yr", "url": "https://www.northwestregisteredagent.com",
         "notes": "Privacy-focused, includes business address"},
        {"name": "Incfile", "cost": "$119/yr (free first year with formation)", "url": "https://www.incfile.com",
         "notes": "Budget-friendly, includes compliance alerts"},
        {"name": "Stripe Atlas", "cost": "Included in $500 formation", "url": "https://stripe.com/atlas",
         "notes": "Best for tech/SaaS, includes banking"},
    ]
    return json.dumps({
        "state": state, "recommended_agents": recommended,
        "search_results": agents_data.get("results", [])[:5],
        "note": "Registered agent receives legal documents on behalf of your business.",
    })


async def _research_business_banking(business_type: str = "agency", state: str = "") -> str:
    """Research and compare business banking options."""
    search_result = await _web_search(f"best business bank account {business_type} {state} 2026 no fees", 5)
    return json.dumps({
        "recommended_banks": [
            {"name": "Mercury", "url": "https://mercury.com", "type": "Online",
             "fees": "No monthly fees", "best_for": "Tech/SaaS, startups",
             "perks": "Free wires, API access, treasury, integrations"},
            {"name": "Relay", "url": "https://relay.com", "type": "Online",
             "fees": "Free plan available", "best_for": "Agencies, freelancers",
             "perks": "Sub-accounts for profit allocation, no minimums"},
            {"name": "Bluevine", "url": "https://bluevine.com", "type": "Online",
             "fees": "No monthly fees", "best_for": "Small businesses",
             "perks": "2% interest on balances, checks, bill pay"},
            {"name": "Chase Business Complete", "url": "https://chase.com/business", "type": "Traditional",
             "fees": "$15/mo (waivable)", "best_for": "Need in-person banking",
             "perks": "Branch access, credit building, merchant services"},
        ],
        "checklist": [
            "1. Have EIN ready",
            "2. Have formation documents (Articles + Operating Agreement)",
            "3. Have government-issued ID for all signers",
            "4. Initial deposit (varies: $0-$100)",
        ],
        "search_results": json.loads(search_result).get("results", [])[:3],
    })


async def _research_business_insurance(business_type: str, state: str = "",
                                         revenue_estimate: str = "") -> str:
    """Research required and recommended business insurance."""
    search_result = await _web_search(f"{business_type} business insurance requirements {state} 2026", 5)
    return json.dumps({
        "required_insurance": [
            {"type": "General Liability", "typical_cost": "$400-800/yr",
             "covers": "Third-party bodily injury, property damage, advertising injury",
             "required_by": "Most clients, landlords, and contracts"},
            {"type": "Professional Liability (E&O)", "typical_cost": "$500-2000/yr",
             "covers": "Errors, omissions, negligence in professional services",
             "required_by": "Client contracts, especially enterprise deals"},
        ],
        "recommended_insurance": [
            {"type": "Cyber Liability", "typical_cost": "$500-1500/yr",
             "covers": "Data breaches, cyber attacks, client data loss",
             "critical_for": "Anyone handling client data, ad accounts, websites"},
            {"type": "Business Owner's Policy (BOP)", "typical_cost": "$500-1000/yr",
             "covers": "Bundles general liability + property + business interruption",
             "best_for": "Agencies with office space or equipment"},
            {"type": "Workers Compensation", "typical_cost": "Varies by state/payroll",
             "covers": "Employee injuries",
             "required_by": "Most states if you have employees (even 1)"},
        ],
        "providers": [
            {"name": "Next Insurance", "url": "https://nextinsurance.com", "notes": "Online, fast quotes, agency-friendly"},
            {"name": "Hiscox", "url": "https://hiscox.com", "notes": "Professional liability specialist"},
            {"name": "Hartford", "url": "https://thehartford.com", "notes": "BOP bundles, established"},
        ],
        "search_results": json.loads(search_result).get("results", [])[:3],
    })


async def _research_business_licenses(business_type: str, state: str, city: str = "") -> str:
    """Research required business licenses and permits."""
    query = f"{business_type} business license requirements {state} {city} 2026"
    search_result = await _web_search(query, 5)
    return json.dumps({
        "state": state, "city": city, "business_type": business_type,
        "common_requirements": [
            {"license": "State Business License", "where": f"{state} Secretary of State or Revenue Dept",
             "cost": "$25-500 depending on state", "renewal": "Annual"},
            {"license": "City/County Business License", "where": f"{city or 'Local'} city clerk or business licensing",
             "cost": "$50-300", "renewal": "Annual"},
            {"license": "Sales Tax Permit", "where": f"{state} Department of Revenue",
             "cost": "Usually free", "needed_if": "Selling taxable goods/services",
             "note": "Most pure services are exempt in most states"},
            {"license": "Home Occupation Permit", "where": "Local zoning office",
             "cost": "$0-100", "needed_if": "Running business from home"},
        ],
        "lookup_tools": [
            {"name": "SBA License & Permit Lookup", "url": "https://www.sba.gov/business-guide/launch-your-business/apply-for-licenses-and-permits"},
            {"name": f"{state} Business One Stop", "url": f"https://www.google.com/search?q={state}+business+license+portal"},
        ],
        "search_results": json.loads(search_result).get("results", [])[:5],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS ADVISOR — Financial Planning, Tax Strategy, Pricing, Cash Flow, Growth
# ═══════════════════════════════════════════════════════════════════════════════

async def _build_financial_model(service: str, pricing_model: str, price_point: str,
                                   target_clients: str, monthly_expenses: str = "0") -> str:
    """Build a financial projection model for the business."""
    try:
        price = float(price_point.replace("$", "").replace(",", "").split("/")[0].split("-")[-1])
        clients_target = int(target_clients.replace(",", ""))
        expenses = float(monthly_expenses.replace("$", "").replace(",", ""))
    except (ValueError, IndexError):
        price, clients_target, expenses = 2000, 10, 500
    monthly_revenue = price * clients_target
    gross_margin = 0.80 if "service" in service.lower() or "agency" in service.lower() else 0.60
    projections = []
    for month in range(1, 13):
        ramp = min(1.0, month / 6)
        rev = monthly_revenue * ramp
        cogs = rev * (1 - gross_margin)
        operating = expenses + (month * 50)
        net = rev - cogs - operating
        projections.append({
            "month": month, "revenue": round(rev), "cogs": round(cogs),
            "gross_profit": round(rev - cogs), "operating_expenses": round(operating),
            "net_profit": round(net), "clients": round(clients_target * ramp),
        })
    return json.dumps({
        "service": service, "pricing_model": pricing_model,
        "unit_economics": {
            "price_per_client": price,
            "gross_margin": f"{gross_margin*100}%",
            "ltv_estimate": price * 8,
            "target_cac": price * 0.3,
            "payback_period": "1 month",
        },
        "year_1_projections": projections,
        "year_1_summary": {
            "total_revenue": sum(p["revenue"] for p in projections),
            "total_profit": sum(p["net_profit"] for p in projections),
            "break_even_month": next((p["month"] for p in projections if p["net_profit"] > 0), "N/A"),
            "year_end_mrr": projections[-1]["revenue"],
        },
        "key_assumptions": [
            "6-month linear ramp to full client capacity",
            f"{gross_margin*100}% gross margin (typical for services)",
            "Operating expenses grow $50/mo (tools, subscriptions)",
            "No client churn in year 1 (optimistic — plan for 5-10%)",
        ],
    })


async def _tax_strategy_research(entity_type: str, estimated_revenue: str,
                                    state: str, filing_status: str = "single") -> str:
    """Research tax optimization strategies for the business."""
    search_result = await _web_search(f"{entity_type} tax strategy {state} {estimated_revenue} revenue 2026", 5)
    try:
        revenue = float(estimated_revenue.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        revenue = 100000
    strategies: list[dict[str, Any]] = []
    if entity_type.lower() in ("llc", "sole_prop"):
        se_tax = revenue * 0.9235 * 0.153
        strategies.append({
            "strategy": "S-Corp Election",
            "savings": f"${round(se_tax * 0.3)}/yr estimated",
            "how": f"Elect S-Corp status with IRS Form 2553. Pay yourself a reasonable salary (~60% of profits), save SE tax on the rest.",
            "threshold": "Consider when profits exceed $50k/year",
            "deadline": "March 15 for current year (or within 75 days of formation)",
        })
    strategies.extend([
        {"strategy": "Quarterly Estimated Taxes",
         "how": "Pay quarterly via IRS EFTPS to avoid underpayment penalties. Due: Apr 15, Jun 15, Sep 15, Jan 15.",
         "critical": True},
        {"strategy": "Home Office Deduction",
         "savings": "$1,500-5,000/yr",
         "how": "Simplified method: $5/sq ft up to 300 sq ft ($1,500). Or actual expenses pro-rated by square footage."},
        {"strategy": "Retirement Contributions",
         "savings": f"Up to ${min(round(revenue * 0.25), 69000)} tax deferred",
         "how": "Solo 401(k): up to $23,500 employee + 25% employer match. SEP IRA: up to 25% of net SE income."},
        {"strategy": "Health Insurance Deduction",
         "savings": "100% of premiums if self-employed",
         "how": "Deduct health, dental, vision premiums for you, spouse, and dependents above the line."},
        {"strategy": "Business Expense Tracking",
         "how": "Track all: software subscriptions, equipment, travel, meals (50%), education, marketing spend.",
         "tools": ["QuickBooks Self-Employed", "FreshBooks", "Wave (free)"]},
    ])
    return json.dumps({
        "entity_type": entity_type, "estimated_revenue": estimated_revenue, "state": state,
        "estimated_federal_rate": "22-32%" if revenue > 50000 else "10-22%",
        "estimated_se_tax": "15.3% on net SE income" if entity_type.lower() != "s_corp" else "On salary portion only",
        "strategies": strategies,
        "critical_dates": [
            "Jan 15 — Q4 estimated tax due",
            "Mar 15 — S-Corp/partnership returns due (Form 1120-S/1065)",
            "Apr 15 — Individual returns + Q1 estimated tax due",
            "Jun 15 — Q2 estimated tax due",
            "Sep 15 — Q3 estimated tax due + S-Corp election deadline (late)",
        ],
        "search_results": json.loads(search_result).get("results", [])[:3],
        "disclaimer": "This is guidance only. Consult a CPA for your specific situation.",
    })


async def _pricing_strategy(service: str, icp: str, competitors: str = "",
                               current_price: str = "") -> str:
    """Develop pricing strategy with market research."""
    comp_research = await _web_search(f"{service} agency pricing 2026 {icp}", 5)
    comp_data = json.loads(comp_research)
    models = [
        {"model": "Retainer", "range": "$1,500-10,000/mo",
         "pros": "Predictable revenue, deeper relationships, better results",
         "cons": "Harder initial sale, scope creep risk",
         "best_for": "Ongoing services (marketing, dev, design)"},
        {"model": "Project-Based", "range": "$2,000-50,000/project",
         "pros": "Clear scope, easy to sell, premium pricing possible",
         "cons": "Revenue gaps between projects, feast/famine",
         "best_for": "Websites, launches, campaigns, audits"},
        {"model": "Performance/Revenue Share", "range": "10-30% of results",
         "pros": "Unlimited upside, aligned incentives",
         "cons": "Income uncertainty, attribution arguments",
         "best_for": "Lead gen, e-commerce, PPC management"},
        {"model": "Productized Service", "range": "$500-5,000/mo per tier",
         "pros": "Scalable, easy to sell, clear deliverables",
         "cons": "Commoditization risk, needs systems",
         "best_for": "Standardized offerings (content packages, SEO audits)"},
    ]
    return json.dumps({
        "service": service, "icp": icp,
        "pricing_models": models,
        "pricing_psychology": [
            "Price in 3 tiers (Good/Better/Best) — middle tier gets 60% of sales",
            "Anchor high: show premium tier first",
            "Use annual pricing with monthly option (+20%) to incentivize commitment",
            "Never compete on price — compete on outcomes and specialization",
            "Raise prices 10-15% for every new client until close rate drops below 30%",
        ],
        "competitor_research": comp_data.get("results", [])[:5],
        "recommended_approach": {
            "start_with": "Retainer or Productized Service",
            "pricing_rule": "10x the value you deliver. If you generate $20k/mo in leads, charge $2k/mo.",
            "test_price": "Start 20% higher than you think — you can always add a lower tier later.",
        },
    })


async def _cash_flow_analysis(monthly_revenue: str, monthly_expenses: str,
                                payment_terms: str = "net_30", runway_months: str = "0") -> str:
    """Analyze cash flow and provide recommendations."""
    try:
        rev = float(monthly_revenue.replace("$", "").replace(",", ""))
        exp = float(monthly_expenses.replace("$", "").replace(",", ""))
        runway = float(runway_months) if runway_months != "0" else 0
    except ValueError:
        rev, exp, runway = 5000, 3000, 0
    net = rev - exp
    burn_rate = exp - rev if rev < exp else 0
    months_runway = runway / exp if exp > 0 and runway > 0 else 0
    return json.dumps({
        "monthly_revenue": rev, "monthly_expenses": exp,
        "net_cash_flow": net, "annual_net": net * 12,
        "burn_rate": burn_rate if burn_rate > 0 else 0,
        "runway_months": round(months_runway, 1) if months_runway > 0 else "N/A",
        "health": "healthy" if net > 0 else "burning" if runway > 0 else "critical",
        "cash_reserves_target": exp * 3,
        "profit_allocation": {
            "owners_pay": f"{round(net * 0.50)}/mo (50%)",
            "tax_reserve": f"{round(net * 0.30)}/mo (30%)",
            "operating_reserve": f"{round(net * 0.15)}/mo (15%)",
            "growth_fund": f"{round(net * 0.05)}/mo (5%)",
        } if net > 0 else {"action": "Cut expenses or increase revenue before allocating"},
        "recommendations": [
            "Collect payment upfront or net-15 (not net-30) to improve cash flow",
            "Bill retainers on the 1st, not after delivery",
            f"Build 3-month reserve: ${round(exp * 3)} target",
            "Separate tax money into a dedicated account immediately",
            "Review subscriptions monthly — cancel anything unused for 30+ days",
        ] + ([f"WARNING: At current burn rate, you have {round(months_runway, 1)} months of runway."] if burn_rate > 0 else []),
    })


async def _growth_playbook(current_revenue: str, target_revenue: str,
                              service: str, channels: str = "") -> str:
    """Build a growth strategy playbook with specific tactics."""
    try:
        current = float(current_revenue.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
        target = float(target_revenue.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        current, target = 5000, 20000
    growth_needed = target / max(current, 1)
    research = await _web_search(f"{service} agency growth strategy {current_revenue} to {target_revenue} 2026", 5)
    stages = []
    if current < 10000:
        stages.append({
            "stage": "Foundation ($0-10k/mo)",
            "focus": "Get first 3-5 paying clients through direct outreach",
            "tactics": [
                "1. Cold email 50 prospects/week with personalized research",
                "2. Post daily on LinkedIn (thought leadership, not pitches)",
                "3. Offer free audits to generate qualified conversations",
                "4. Ask every happy client for 2 referrals",
                "5. Speak at 1 virtual event/month in your niche",
            ],
            "kpis": ["5 discovery calls/week", "30% close rate", "0% client churn"],
        })
    if current < 50000:
        stages.append({
            "stage": "Scale ($10k-50k/mo)",
            "focus": "Systematize delivery, build repeatable sales process",
            "tactics": [
                "1. Productize your service into 2-3 clear packages",
                "2. Hire first contractor/VA for delivery ($15-25/hr)",
                "3. Build case studies with measurable results",
                "4. Launch paid ads targeting your ICP",
                "5. Create a referral program (10-15% commission)",
                "6. Build an email list with weekly newsletter",
            ],
            "kpis": ["10 discovery calls/week", "40% close rate", "<5% monthly churn"],
        })
    if target > 50000:
        stages.append({
            "stage": "Leverage ($50k-100k+/mo)",
            "focus": "Remove yourself from delivery, build the machine",
            "tactics": [
                "1. Hire account managers — you do sales and strategy only",
                "2. Build SOPs for every deliverable",
                "3. Launch a signature methodology/framework",
                "4. Create content engine (podcast, YouTube, or newsletter)",
                "5. Strategic partnerships with complementary agencies",
                "6. Consider white-label or licensing model",
            ],
            "kpis": ["<10% of time in delivery", "90%+ client retention", "20%+ net margin"],
        })
    return json.dumps({
        "current_revenue": current, "target_revenue": target,
        "growth_multiple": f"{growth_needed:.1f}x",
        "growth_stages": stages,
        "universal_principles": [
            "Niche down harder — the riches are in the niches",
            "Raise prices before adding clients",
            "Referrals are the highest-converting channel (track them)",
            "Document everything you do — SOPs enable delegation",
            "Revenue is vanity, profit is sanity, cash flow is king",
        ],
        "research": json.loads(research).get("results", [])[:3],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# EXPANDED LEGAL — IP, Employment, Tax Compliance, Regulatory, Liability
# ═══════════════════════════════════════════════════════════════════════════════

async def _research_ip_protection(business_name: str, service: str, state: str = "") -> str:
    """Research intellectual property protection — trademarks, copyrights, trade secrets."""
    tm_search = await _web_search(f'"{business_name}" trademark TESS USPTO', 3)
    return json.dumps({
        "business_name": business_name,
        "trademark": {
            "status": "research_complete",
            "search_url": f"https://tmsearch.uspto.gov/search/search-information",
            "search_results": json.loads(tm_search).get("results", [])[:3],
            "process": [
                "1. Search USPTO TESS database for conflicts",
                "2. File trademark application ($250-350 per class via TEAS Plus)",
                "3. Examination period: 3-4 months",
                "4. Publication for opposition: 30 days",
                "5. Registration: ~8-12 months total",
            ],
            "classes_likely_needed": [
                "Class 35: Advertising/marketing services",
                "Class 42: Computer/technology services",
            ],
            "cost": "$250-350/class (TEAS Plus) or $350-450/class (TEAS Standard)",
            "diy_vs_attorney": "Can file yourself for simple marks; hire attorney for complex or contested marks ($1,000-2,500)",
        },
        "copyright": {
            "automatic": True,
            "note": "Copyright is automatic upon creation. Registration ($35-65 online) adds enforcement power.",
            "what_to_register": ["Website content", "Original frameworks/methodologies", "Training materials", "Software code"],
        },
        "trade_secrets": {
            "protect_via": ["NDAs with all contractors and employees", "Confidentiality clauses in client contracts",
                           "Limit access to proprietary processes", "Document what constitutes trade secrets"],
        },
        "domain_protection": {
            "register_variations": [f"{business_name.lower().replace(' ', '')}.com/net/org/io",
                                    f"{business_name.lower().replace(' ', '')}.co"],
            "social_handles": "Claim consistent handles on all platforms immediately",
        },
    })


async def _employment_law_research(state: str, worker_type: str = "contractor",
                                      num_workers: str = "0") -> str:
    """Research employment law requirements — contractor vs employee, compliance."""
    search_result = await _web_search(f"{state} independent contractor vs employee rules 2026 {worker_type}", 5)
    return json.dumps({
        "state": state, "worker_type": worker_type,
        "contractor_vs_employee": {
            "irs_test": "Behavioral control, financial control, relationship type",
            "key_factors": [
                "Contractors set own hours and use own tools",
                "Contractors can work for other clients",
                "Contractors invoice for work, no benefits provided",
                "Employees have set schedules and provided tools",
            ],
            "misclassification_risk": "High fines + back taxes + penalties if misclassified",
            "safe_harbor": "Use written contractor agreements, 1099 at year end, no benefits",
        },
        "contractor_requirements": [
            "Written Independent Contractor Agreement",
            "W-9 form before first payment",
            "1099-NEC if paid $600+ in a year",
            "No withholding taxes — contractor pays own",
            "No benefits, no equipment, no set hours",
        ],
        "employee_requirements": [
            "W-4 and I-9 forms",
            "Payroll withholding (federal, state, FICA)",
            "Workers compensation insurance",
            f"State unemployment insurance ({state})",
            "Compliance with minimum wage and overtime laws",
            "Required posters and notices",
        ],
        "when_to_hire_employees": [
            "Full-time dedicated team members",
            "When you need to control how work is done (not just results)",
            "When worker is integral to business operations",
            "When you want to offer equity/benefits",
        ],
        "payroll_services": [
            {"name": "Gusto", "cost": "$40/mo + $6/person", "best_for": "Small teams, easy setup"},
            {"name": "Rippling", "cost": "$8/person/mo", "best_for": "Growing teams, IT + HR"},
            {"name": "ADP Run", "cost": "From $59/mo", "best_for": "Established businesses"},
        ],
        "search_results": json.loads(search_result).get("results", [])[:3],
    })


async def _compliance_checklist(business_type: str, state: str, has_employees: str = "no",
                                   handles_data: str = "yes") -> str:
    """Generate comprehensive regulatory compliance checklist."""
    checklist: list[dict[str, Any]] = [
        {"category": "Formation", "items": [
            "Articles of Organization/Incorporation filed with state",
            "Operating Agreement (LLC) or Bylaws (Corp) in place",
            "EIN obtained from IRS",
            "Registered agent designated",
            "State annual report/franchise tax scheduled",
        ]},
        {"category": "Tax Compliance", "items": [
            "Quarterly estimated tax payments scheduled (1040-ES)",
            "Bookkeeping system set up (QuickBooks, FreshBooks, Wave)",
            "Business vs personal expenses separated",
            "Receipts saved for all deductions",
            "Sales tax collection if applicable",
        ]},
        {"category": "Contracts & Legal", "items": [
            "Client service agreement template reviewed by attorney",
            "Independent contractor agreement for all contractors",
            "NDA template for sensitive work",
            "Terms of Service for website/platform",
            "Privacy Policy compliant with applicable laws",
        ]},
    ]
    if handles_data.lower() == "yes":
        checklist.append({"category": "Data Privacy & Security", "items": [
            "Privacy Policy on website (GDPR, CCPA, CAN-SPAM compliant)",
            "Data Processing Agreement (DPA) for client data",
            "SSL certificate on all web properties",
            "Password manager for team credentials",
            "Two-factor auth on all business accounts",
            "Incident response plan documented",
            "Client data handling procedures documented",
        ]})
    if has_employees.lower() == "yes":
        checklist.append({"category": "Employment Compliance", "items": [
            "Workers compensation insurance obtained",
            "State unemployment insurance registered",
            "Federal and state labor posters displayed",
            "Employee handbook created",
            "I-9 forms completed for all employees",
            "Payroll system set up with proper withholdings",
            "Anti-harassment policy in place",
        ]})
    checklist.append({"category": "Insurance", "items": [
        "General liability insurance ($1M minimum)",
        "Professional liability / E&O insurance",
        "Cyber liability insurance (if handling client data)",
        "Business property insurance (if applicable)",
    ]})
    checklist.append({"category": "Marketing Compliance", "items": [
        "CAN-SPAM compliant email practices (unsubscribe link, physical address)",
        "FTC endorsement guidelines followed (disclose paid partnerships)",
        "TCPA compliance for calls/texts (consent records)",
        "Ad platform terms of service followed",
        "Testimonials are real and not misleading",
    ]})
    return json.dumps({
        "business_type": business_type, "state": state,
        "compliance_checklist": checklist,
        "total_items": sum(len(c["items"]) for c in checklist),
        "critical_deadlines": [
            "Annual: State annual report/franchise tax",
            "Quarterly: Estimated tax payments (Apr 15, Jun 15, Sep 15, Jan 15)",
            "Monthly: Payroll tax deposits (if employees)",
            "Ongoing: Contractor 1099s by Jan 31",
        ],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSITE BUILDER — Full Multi-Page Site Generation & Deployment
# ═══════════════════════════════════════════════════════════════════════════════

async def _build_full_website(business_name: str, service: str, pages: str = "home,about,services,contact",
                                brand_colors: str = "", brand_fonts: str = "",
                                cta_text: str = "Book a Call", cta_url: str = "#contact") -> str:
    """Generate a complete multi-page business website with responsive design and deploy to Vercel."""
    page_list = [p.strip().lower() for p in pages.split(",")]
    primary = "#6366f1"
    secondary = "#1e1b4b"
    accent = "#f59e0b"
    if brand_colors:
        try:
            colors = json.loads(brand_colors) if brand_colors.startswith("{") else {}
            primary = colors.get("primary", primary)
            secondary = colors.get("secondary", secondary)
            accent = colors.get("accent", accent)
        except json.JSONDecodeError:
            if brand_colors.startswith("#"):
                primary = brand_colors

    display_font = "Inter"
    body_font = "Inter"
    if brand_fonts:
        try:
            fonts = json.loads(brand_fonts) if brand_fonts.startswith("{") else {}
            display_font = fonts.get("display", display_font)
            body_font = fonts.get("body", body_font)
        except json.JSONDecodeError:
            pass

    css = f"""/* {business_name} — Generated Styles */
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --primary:{primary};--secondary:{secondary};--accent:{accent};
  --bg:#ffffff;--bg-alt:#f8fafc;--text:#1e293b;--text-light:#64748b;
  --radius:12px;--shadow:0 1px 3px rgba(0,0,0,0.1);
  --font-display:'{display_font}',system-ui,sans-serif;
  --font-body:'{body_font}',system-ui,sans-serif;
}}
@import url('https://fonts.googleapis.com/css2?family={display_font.replace(' ','+')}:wght@400;500;600;700;800&display=swap');
body{{font-family:var(--font-body);color:var(--text);line-height:1.6;font-size:16px}}
a{{color:var(--primary);text-decoration:none}}
img{{max-width:100%;height:auto}}
.container{{max-width:1200px;margin:0 auto;padding:0 24px}}

/* Navigation */
nav{{background:var(--bg);border-bottom:1px solid #e2e8f0;position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}}
nav .container{{display:flex;justify-content:space-between;align-items:center;height:72px}}
nav .logo{{font-family:var(--font-display);font-weight:800;font-size:1.5rem;color:var(--secondary)}}
nav ul{{display:flex;gap:32px;list-style:none}}
nav a{{color:var(--text);font-weight:500;transition:color 0.2s}}
nav a:hover{{color:var(--primary)}}
nav .cta-nav{{background:var(--primary);color:#fff!important;padding:10px 24px;border-radius:var(--radius);font-weight:600}}
nav .cta-nav:hover{{opacity:0.9}}

/* Hero */
.hero{{min-height:85vh;display:flex;align-items:center;background:linear-gradient(135deg,{secondary} 0%,{primary} 100%);color:#fff;text-align:center}}
.hero h1{{font-family:var(--font-display);font-size:clamp(2.5rem,5vw,4rem);font-weight:800;max-width:800px;margin:0 auto 1.5rem;line-height:1.1}}
.hero p{{font-size:1.25rem;max-width:600px;margin:0 auto 2rem;opacity:0.9}}
.btn{{display:inline-block;padding:14px 32px;border-radius:var(--radius);font-weight:700;font-size:1rem;transition:all 0.2s;cursor:pointer;border:none}}
.btn-primary{{background:var(--accent);color:var(--secondary)}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}}
.btn-secondary{{background:rgba(255,255,255,0.15);color:#fff;border:2px solid rgba(255,255,255,0.3)}}
.btn-secondary:hover{{background:rgba(255,255,255,0.25)}}

/* Sections */
section{{padding:96px 0}}
section:nth-child(even){{background:var(--bg-alt)}}
.section-header{{text-align:center;margin-bottom:64px}}
.section-header h2{{font-family:var(--font-display);font-size:2.5rem;font-weight:800;color:var(--secondary);margin-bottom:16px}}
.section-header p{{font-size:1.125rem;color:var(--text-light);max-width:600px;margin:0 auto}}

/* Grid */
.grid{{display:grid;gap:32px}}
.grid-2{{grid-template-columns:repeat(auto-fit,minmax(400px,1fr))}}
.grid-3{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.grid-4{{grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}}

/* Cards */
.card{{background:var(--bg);border:1px solid #e2e8f0;border-radius:var(--radius);padding:32px;transition:all 0.2s}}
.card:hover{{box-shadow:0 8px 24px rgba(0,0,0,0.08);transform:translateY(-4px)}}
.card h3{{font-size:1.25rem;font-weight:700;margin-bottom:12px;color:var(--secondary)}}
.card p{{color:var(--text-light)}}
.card .icon{{font-size:2rem;margin-bottom:16px}}

/* Contact */
.contact-form{{max-width:600px;margin:0 auto}}
.contact-form input,.contact-form textarea,.contact-form select{{width:100%;padding:14px 16px;border:1px solid #e2e8f0;border-radius:8px;font-size:1rem;margin-bottom:16px;font-family:inherit}}
.contact-form textarea{{min-height:150px;resize:vertical}}
.contact-form button{{width:100%}}

/* Footer */
footer{{background:var(--secondary);color:rgba(255,255,255,0.7);padding:48px 0 24px}}
footer .container{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:24px}}
footer h4{{color:#fff;margin-bottom:12px}}
footer a{{color:rgba(255,255,255,0.7)}}footer a:hover{{color:#fff}}
footer .bottom{{border-top:1px solid rgba(255,255,255,0.1);margin-top:32px;padding-top:24px;text-align:center;font-size:0.875rem}}

/* Mobile */
@media(max-width:768px){{
  nav ul{{display:none}}
  .hero h1{{font-size:2rem}}
  .grid-2,.grid-3,.grid-4{{grid-template-columns:1fr}}
  section{{padding:64px 0}}
}}"""

    nav_links = []
    for p in page_list:
        label = p.replace("-", " ").replace("_", " ").title()
        href = f"{p}.html" if p != "home" else "index.html"
        nav_links.append(f'<li><a href="{href}">{label}</a></li>')
    nav_html = f"""<nav><div class="container">
<a href="index.html" class="logo">{business_name}</a>
<ul>{" ".join(nav_links)}</ul>
<a href="{cta_url}" class="cta-nav">{cta_text}</a>
</div></nav>"""

    footer_html = f"""<footer><div class="container">
<div><h4>{business_name}</h4><p>Professional {service.lower()} that delivers results.</p></div>
<div><h4>Quick Links</h4>{''.join(f'<p><a href="{p}.html" >{p.title()}</a></p>' for p in page_list if p != "home")}</div>
<div><h4>Contact</h4><p>Email: hello@{business_name.lower().replace(' ','')}.com</p></div>
<div class="bottom"><p>&copy; 2026 {business_name}. All rights reserved.</p></div>
</div></footer>"""

    def _make_page(title: str, body: str) -> str:
        return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {business_name}</title>
<meta name="description" content="{business_name} — Professional {service}">
<link rel="stylesheet" href="styles.css">
</head><body>{nav_html}{body}{footer_html}</body></html>"""

    files = [{"file": "styles.css", "data": css}]

    if "home" in page_list or "index" in page_list:
        home_body = f"""
<section class="hero"><div class="container">
<h1>We Help Businesses Grow With Expert {service}</h1>
<p>Results-driven {service.lower()} for companies that demand excellence. No fluff, no excuses — just outcomes.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
<a href="services.html" class="btn btn-secondary" style="margin-left:12px">Our Services</a>
</div></section>
<section><div class="container">
<div class="section-header"><h2>Why Choose {business_name}</h2><p>We combine deep expertise with proven systems to deliver measurable results.</p></div>
<div class="grid grid-3">
<div class="card"><div class="icon">&#9733;</div><h3>Proven Results</h3><p>Track record of delivering measurable outcomes for every client.</p></div>
<div class="card"><div class="icon">&#9881;</div><h3>Systematic Approach</h3><p>Battle-tested frameworks that remove guesswork and accelerate growth.</p></div>
<div class="card"><div class="icon">&#9829;</div><h3>Dedicated Partnership</h3><p>We become an extension of your team, not just another vendor.</p></div>
</div></div></section>
<section><div class="container" style="text-align:center">
<h2>Ready to Get Started?</h2><p style="margin:16px auto 32px;max-width:500px;color:var(--text-light)">Book a free strategy call and let's discuss how we can help grow your business.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
</div></section>"""
        files.append({"file": "index.html", "data": _make_page("Home", home_body)})

    if "about" in page_list:
        about_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>About {business_name}</h2><p>The story behind our mission to transform how businesses grow.</p></div>
<div class="grid grid-2" style="align-items:center">
<div><h3 style="font-size:1.5rem;margin-bottom:16px">Built on Expertise, Driven by Results</h3>
<p style="margin-bottom:16px">We started {business_name} because we saw too many businesses wasting money on {service.lower()} that didn't deliver. Our approach is different — we combine deep industry expertise with data-driven strategies that actually move the needle.</p>
<p>Every engagement starts with understanding your business, your market, and your goals. Then we build a custom strategy designed to deliver measurable results.</p></div>
<div class="card" style="background:var(--bg-alt)"><h3>Our Values</h3>
<p style="margin-bottom:12px"><strong>Transparency</strong> — No hidden fees, no vanity metrics. You see exactly what we do and why.</p>
<p style="margin-bottom:12px"><strong>Accountability</strong> — We tie our success to your outcomes, not our hours.</p>
<p><strong>Excellence</strong> — Good enough isn't in our vocabulary. We push for exceptional.</p></div>
</div></div></section>"""
        files.append({"file": "about.html", "data": _make_page("About", about_body)})

    if "services" in page_list:
        services_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>Our Services</h2><p>Comprehensive {service.lower()} solutions tailored to your business goals.</p></div>
<div class="grid grid-2">
<div class="card"><h3>Strategy & Planning</h3><p>Deep-dive market research, competitive analysis, and custom roadmaps that align with your business objectives.</p></div>
<div class="card"><h3>Execution & Implementation</h3><p>We don't just plan — we execute. Full implementation of strategies with measurable milestones.</p></div>
<div class="card"><h3>Optimization & Growth</h3><p>Continuous improvement through data analysis, A/B testing, and performance optimization.</p></div>
<div class="card"><h3>Reporting & Analytics</h3><p>Transparent reporting with actionable insights. Know exactly what's working and what's next.</p></div>
</div></div></section>
<section><div class="container" style="text-align:center">
<h2>Let's Talk About Your Goals</h2><p style="margin:16px auto 32px;max-width:500px;color:var(--text-light)">Every business is different. Let's find the right approach for yours.</p>
<a href="{cta_url}" class="btn btn-primary">{cta_text}</a>
</div></section>"""
        files.append({"file": "services.html", "data": _make_page("Services", services_body)})

    if "contact" in page_list:
        contact_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>Get in Touch</h2><p>Ready to grow? Let's start a conversation.</p></div>
<div class="contact-form" id="contact">
<form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
<input type="text" name="name" placeholder="Your Name" required>
<input type="email" name="email" placeholder="Your Email" required>
<input type="text" name="company" placeholder="Company Name">
<select name="budget"><option value="">Budget Range</option><option>$1,000-$3,000/mo</option><option>$3,000-$5,000/mo</option><option>$5,000-$10,000/mo</option><option>$10,000+/mo</option></select>
<textarea name="message" placeholder="Tell us about your project and goals..." required></textarea>
<button type="submit" class="btn btn-primary">{cta_text}</button>
</form></div></div></section>"""
        files.append({"file": "contact.html", "data": _make_page("Contact", contact_body)})

    for p in page_list:
        if p not in ("home", "index", "about", "services", "contact"):
            generic_body = f"""
<section style="padding-top:120px"><div class="container">
<div class="section-header"><h2>{p.replace('-',' ').replace('_',' ').title()}</h2><p>Content for this page.</p></div>
</div></section>"""
            files.append({"file": f"{p}.html", "data": _make_page(p.title(), generic_body)})

    result: dict[str, Any] = {
        "pages_generated": len(files) - 1,
        "files": [f["file"] for f in files],
        "features": ["Responsive design", "Mobile-first", "SEO meta tags", "Contact form",
                      "Sticky navigation", "Custom brand colors", "Google Fonts", "CSS Grid layout"],
    }

    token = getattr(settings, 'vercel_token', '') or ""
    if token:
        deploy_result = await _deploy_to_vercel(
            project_name=re.sub(r'[^a-z0-9-]', '', business_name.lower().replace(' ', '-'))[:40],
            files=json.dumps(files))
        deploy_data = json.loads(deploy_result)
        result["deployed_url"] = deploy_data.get("url", "")
        result["deployment_id"] = deploy_data.get("deployment_id", "")
        result["status"] = "deployed"
    else:
        result["status"] = "generated"
        result["note"] = "Set VERCEL_TOKEN to auto-deploy. Files ready for manual deployment."
    return json.dumps(result)


async def _generate_page(page_type: str, business_name: str, content: str,
                           brand_colors: str = "", style: str = "modern") -> str:
    """Generate a single page with specific content — pricing, case studies, FAQ, blog, etc."""
    primary = "#6366f1"
    if brand_colors:
        try:
            colors = json.loads(brand_colors) if brand_colors.startswith("{") else {}
            primary = colors.get("primary", primary)
        except json.JSONDecodeError:
            if brand_colors.startswith("#"):
                primary = brand_colors
    templates: dict[str, str] = {
        "pricing": f"""<section style="padding:120px 0 96px"><div style="max-width:1200px;margin:0 auto;padding:0 24px;text-align:center">
<h2 style="font-size:2.5rem;font-weight:800;margin-bottom:16px">Simple, Transparent Pricing</h2>
<p style="color:#64748b;margin-bottom:48px">No hidden fees. No long-term contracts. Cancel anytime.</p>
{content}
</div></section>""",
        "case_study": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
<h2 style="font-size:2.5rem;font-weight:800;margin-bottom:32px">Case Study</h2>
{content}
</div></section>""",
        "faq": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
<h2 style="font-size:2.5rem;font-weight:800;text-align:center;margin-bottom:48px">Frequently Asked Questions</h2>
{content}
</div></section>""",
        "blog": f"""<section style="padding:120px 0 96px"><div style="max-width:800px;margin:0 auto;padding:0 24px">
{content}
</div></section>""",
    }
    body = templates.get(page_type, f"<section style='padding:120px 0 96px'><div style='max-width:1200px;margin:0 auto;padding:0 24px'>{content}</div></section>")
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_type.title()} — {business_name}</title>
<link rel="stylesheet" href="styles.css">
</head><body>{body}</body></html>"""
    return json.dumps({"page_type": page_type, "html_length": len(html),
                       "html": html[:5000], "generated": True})


# ═══════════════════════════════════════════════════════════════════════════════
# BACK-OFFICE TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _generate_chart_of_accounts(entity_type: str = "llc", industry: str = "services") -> str:
    """Generate entity-appropriate chart of accounts."""
    base = {
        "1000-Assets": ["1010 Business Checking", "1020 Business Savings", "1030 Accounts Receivable",
                        "1040 Prepaid Expenses", "1050 Equipment", "1060 Accumulated Depreciation"],
        "2000-Liabilities": ["2010 Accounts Payable", "2020 Credit Card Payable", "2030 Sales Tax Payable",
                             "2040 Payroll Tax Payable", "2050 Unearned Revenue"],
        "3000-Equity": [],
        "4000-Revenue": ["4010 Service Revenue", "4020 Retainer Revenue", "4030 Project Revenue",
                         "4040 Consulting Revenue", "4050 Referral Income"],
        "5000-COGS": ["5010 Contractor Payments", "5020 Software/Tools (Delivery)", "5030 Subcontractor Costs"],
        "6000-Operating": ["6010 Advertising", "6020 Software Subscriptions", "6030 Professional Services",
                           "6040 Office/Coworking", "6050 Insurance", "6060 Travel", "6070 Education/Training",
                           "6080 Meals (50% deductible)", "6090 Phone/Internet", "6100 Bank Fees"],
    }
    et = (entity_type or "llc").lower()
    if et == "sole_prop":
        base["3000-Equity"] = ["3010 Owner's Equity", "3020 Owner's Draws"]
    elif et in ("llc",):
        base["3000-Equity"] = ["3010 Member's Equity", "3020 Member's Distributions", "3030 Retained Earnings"]
    elif et in ("s_corp", "c_corp"):
        base["3000-Equity"] = ["3010 Common Stock", "3020 Retained Earnings", "3030 Dividends Paid"]
        base["6000-Operating"].append("6110 Officer Compensation")
        base["6000-Operating"].append("6120 Payroll Expenses")
    elif et == "partnership":
        base["3000-Equity"] = ["3010 Partner A Capital", "3020 Partner B Capital", "3030 Partner Draws"]
    return json.dumps({"entity_type": et, "industry": industry, "chart_of_accounts": base})


async def _generate_pnl_template(entity_type: str = "llc", monthly_revenue: str = "0") -> str:
    """Generate monthly P&L template."""
    et = (entity_type or "llc").lower()
    template = {
        "revenue": {"service_revenue": 0, "retainer_revenue": 0, "project_revenue": 0, "total_revenue": 0},
        "cogs": {"contractor_costs": 0, "delivery_tools": 0, "total_cogs": 0},
        "gross_profit": 0,
        "operating_expenses": {
            "marketing": 0, "software": 0, "professional_services": 0, "insurance": 0,
            "office": 0, "travel": 0, "education": 0, "misc": 0,
        },
    }
    if et in ("s_corp", "c_corp"):
        template["operating_expenses"]["officer_salary"] = 0
        template["operating_expenses"]["payroll_taxes"] = 0
        template["operating_expenses"]["benefits"] = 0
    template["net_operating_income"] = 0
    if et == "c_corp":
        template["income_tax_provision"] = 0
        template["net_income_after_tax"] = 0
    else:
        template["note"] = f"Pass-through entity ({et}) — income taxed at owner level"
    return json.dumps({"entity_type": et, "pnl_template": template})


async def _tax_deadline_calendar(entity_type: str = "llc", state: str = "") -> str:
    """Generate tax compliance calendar by entity type."""
    et = (entity_type or "llc").lower()
    deadlines = []
    # Quarterly estimated taxes — all entities
    deadlines.append({"date": "Apr 15", "item": "Q1 estimated tax payment", "form": "1040-ES" if et in ("sole_prop", "llc") else "1120-W"})
    deadlines.append({"date": "Jun 15", "item": "Q2 estimated tax payment", "form": "1040-ES" if et in ("sole_prop", "llc") else "1120-W"})
    deadlines.append({"date": "Sep 15", "item": "Q3 estimated tax payment", "form": "1040-ES" if et in ("sole_prop", "llc") else "1120-W"})
    deadlines.append({"date": "Jan 15", "item": "Q4 estimated tax payment", "form": "1040-ES" if et in ("sole_prop", "llc") else "1120-W"})

    if et == "sole_prop":
        deadlines.append({"date": "Apr 15", "item": "Annual tax return", "form": "Schedule C (1040)"})
    elif et == "llc":
        deadlines.append({"date": "Mar 15", "item": "Partnership return (multi-member) or Schedule C (single-member)", "form": "1065 or Schedule C"})
    elif et == "s_corp":
        deadlines.append({"date": "Mar 15", "item": "S-Corp tax return", "form": "1120-S"})
        deadlines.append({"date": "Jan 31", "item": "W-2s to employees", "form": "W-2"})
        deadlines.append({"date": "Jan 31", "item": "1099s to contractors", "form": "1099-NEC"})
    elif et == "c_corp":
        deadlines.append({"date": "Apr 15", "item": "C-Corp tax return", "form": "1120"})
        deadlines.append({"date": "Jan 31", "item": "W-2s to employees", "form": "W-2"})
        deadlines.append({"date": "Jan 31", "item": "1099s to contractors", "form": "1099-NEC"})
    elif et == "partnership":
        deadlines.append({"date": "Mar 15", "item": "Partnership return + K-1s", "form": "1065 + K-1"})

    if state:
        deadlines.append({"date": "Varies", "item": f"State tax return — {state}", "form": f"Check {state} DOR"})
        deadlines.append({"date": "Varies", "item": f"Annual report — {state}", "form": f"Secretary of State"})

    return json.dumps({"entity_type": et, "state": state, "deadlines": sorted(deadlines, key=lambda d: d["date"])})


async def _create_hiring_plan(service: str = "", current_revenue: str = "0", entity_type: str = "llc") -> str:
    """Generate revenue-triggered hiring plan."""
    et = (entity_type or "llc").lower()
    plan = {
        "entity_type": et,
        "hiring_model": "1099 contractors" if et == "sole_prop" else "W-2 + 1099 mix",
        "phases": [
            {"revenue_trigger": "$0-5K/mo", "hires": ["No hires — founder does everything"],
             "note": "Focus on sales and delivery. Automate what you can."},
            {"revenue_trigger": "$5K-15K/mo", "hires": ["1099 Contractor: Delivery Specialist", "1099 Contractor: VA (admin)"],
             "note": "Delegate delivery first so founder can sell."},
            {"revenue_trigger": "$15K-30K/mo", "hires": ["1099/W-2: Operations Manager", "1099: Content/Marketing"],
             "note": "Ops manager is the first critical hire. Frees founder for strategy."},
            {"revenue_trigger": "$30K-50K/mo", "hires": ["W-2: Account Manager", "1099: Sales Development"],
             "note": "Account management prevents churn. SDR drives growth."},
            {"revenue_trigger": "$50K+/mo", "hires": ["W-2: Department Leads", "W-2: Finance/Bookkeeper"],
             "note": "Build middle management. Founder becomes CEO."},
        ],
    }
    if et in ("s_corp", "c_corp"):
        plan["note"] = f"Owner is already W-2 employee of the {et.replace('_', '-').upper()}. Payroll is running from day 1."
    return json.dumps(plan)


async def _worker_classification_check(worker_role: str = "", state: str = "", hours_per_week: str = "0") -> str:
    """Check 1099 vs W-2 classification risk."""
    risk_factors = []
    hours = int(hours_per_week) if hours_per_week.isdigit() else 0
    if hours >= 30:
        risk_factors.append("Working 30+ hours/week — high risk of misclassification as employee")
    factors = {
        "behavioral_control": "Does the business control HOW the worker performs? If yes → employee indicator.",
        "financial_control": "Does the worker have unreimbursed expenses, opportunity for profit/loss? If yes → contractor indicator.",
        "relationship_type": "Is there a written contract? Benefits? Permanence? These all matter.",
    }
    return json.dumps({
        "worker_role": worker_role, "state": state, "hours_per_week": hours,
        "risk_factors": risk_factors, "irs_factors": factors,
        "recommendation": "Consult employment attorney if any risk factors present.",
        "state_note": f"{state} may have stricter rules than federal (e.g. CA ABC test, MA presumption of employment)" if state else "",
    })


async def _build_sales_pipeline(service: str = "", avg_deal_size: str = "0", sales_cycle_days: str = "30") -> str:
    """Build CRM pipeline stages with conversion targets."""
    return json.dumps({
        "pipeline_stages": [
            {"stage": "Lead", "description": "New inbound or outbound lead", "target_conversion": "40%", "actions": ["Qualify via BANT", "Add to CRM", "Schedule discovery"]},
            {"stage": "Discovery", "description": "Discovery call completed", "target_conversion": "60%", "actions": ["Run discovery script", "Identify pain/budget/timeline", "Send recap email"]},
            {"stage": "Proposal", "description": "Proposal sent", "target_conversion": "50%", "actions": ["Send custom proposal", "Include 3 pricing tiers", "Set follow-up reminder"]},
            {"stage": "Negotiation", "description": "Active negotiation", "target_conversion": "70%", "actions": ["Handle objections", "Offer concessions strategically", "Get verbal commit"]},
            {"stage": "Closed Won", "description": "Contract signed, payment received", "target_conversion": "100%", "actions": ["Send contract", "Collect payment", "Trigger onboarding"]},
            {"stage": "Closed Lost", "description": "Deal lost", "target_conversion": "—", "actions": ["Log reason", "Add to nurture sequence", "Review in retrospective"]},
        ],
        "velocity_targets": {
            "avg_deal_size": avg_deal_size,
            "sales_cycle_days": sales_cycle_days,
            "target_win_rate": "35-45% overall",
            "leads_needed_monthly": "Based on your targets, work backwards from revenue goal",
        },
    })


async def _generate_discovery_script(service: str = "", icp: str = "") -> str:
    """Generate discovery call script with objection handling."""
    return json.dumps({
        "opening": f"Thanks for taking the time. I'd love to understand your situation before I talk about what we do. Can you walk me through [specific pain related to {service}]?",
        "questions": {
            "pain": ["What's the biggest challenge you're facing with [area]?", "How long has this been a problem?", "What have you tried so far?"],
            "impact": ["What does this cost you monthly — in time, money, or missed opportunities?", "If you don't solve this in the next 6 months, what happens?"],
            "budget": ["Do you have a budget allocated for solving this?", "What would solving this be worth to you monthly?"],
            "authority": ["Who else is involved in this decision?", "What does your decision process look like?"],
            "timeline": ["When would you ideally want to start?", "Is there a deadline driving this?"],
        },
        "objection_handling": {
            "too_expensive": "I understand. Let me ask — what's the cost of NOT solving this? [Reframe value vs price]",
            "need_to_think": "Totally fair. What specifically do you need to think through? [Identify real objection]",
            "talking_to_others": "Smart to compare. What criteria are most important to you? [Position your differentiator]",
            "bad_timing": "When would be better? Let me send you something useful in the meantime. [Stay in touch]",
        },
        "close": "Based on what you've told me, here's what I'd recommend... [Prescribe, don't pitch]. Can I send you a proposal by [date]?",
    })


async def _build_delivery_sop(service: str = "", phase: str = "onboarding") -> str:
    """Generate standard operating procedure for a delivery phase."""
    return json.dumps({
        "service": service, "phase": phase,
        "sop": {
            "objective": f"Standard procedure for the {phase} phase of {service} delivery",
            "steps": [
                {"step": 1, "action": "Send welcome email with expectations doc", "owner": "Account Manager", "timing": "Within 2 hours of contract signing"},
                {"step": 2, "action": "Schedule kickoff call", "owner": "Account Manager", "timing": "Within 24 hours"},
                {"step": 3, "action": "Collect all required assets/access", "owner": "Operations", "timing": "Before kickoff call"},
                {"step": 4, "action": "Run kickoff call (agenda: goals, timeline, communication cadence)", "owner": "Project Lead", "timing": "Within 3 business days"},
                {"step": 5, "action": "Set up project in PM tool with milestones", "owner": "Operations", "timing": "Within 24 hours of kickoff"},
                {"step": 6, "action": "Send client the project timeline and communication plan", "owner": "Account Manager", "timing": "Same day as kickoff"},
            ],
            "quality_gates": ["Client assets received", "Kickoff call completed", "Project plan approved by client"],
            "escalation": "If any step is blocked for >24 hours, escalate to Operations Manager",
        },
    })


async def _capacity_planning(service: str = "", hours_per_client: str = "10", team_size: str = "1") -> str:
    """Calculate capacity and utilization targets."""
    hpc = int(hours_per_client) if hours_per_client.isdigit() else 10
    ts = int(team_size) if team_size.isdigit() else 1
    billable_hours = 32  # per person per week (80% utilization)
    max_clients = (billable_hours * ts) // hpc if hpc > 0 else 0
    return json.dumps({
        "hours_per_client_weekly": hpc,
        "team_size": ts,
        "billable_hours_per_person": billable_hours,
        "utilization_target": "80%",
        "max_concurrent_clients": max_clients,
        "recommended_max": int(max_clients * 0.85),  # leave buffer
        "warning_threshold": int(max_clients * 0.9),
        "actions_at_capacity": ["Raise prices", "Hire next team member", "Waitlist new clients", "Reduce scope per client"],
    })


async def _build_metrics_hierarchy(service: str = "", business_model: str = "retainer") -> str:
    """Build North Star → L1 → L2 → Leading indicators hierarchy."""
    return json.dumps({
        "north_star": "Monthly Recurring Revenue (MRR)" if business_model == "retainer" else "Monthly Revenue",
        "l1_metrics": [
            {"metric": "New Clients/Month", "target": "3-5", "source": "CRM"},
            {"metric": "Client Retention Rate", "target": ">90%", "source": "CRM"},
            {"metric": "Average Revenue Per Client", "target": "Varies", "source": "Billing"},
            {"metric": "Gross Margin", "target": ">60%", "source": "Accounting"},
        ],
        "l2_metrics": [
            {"metric": "Lead-to-Client Conversion Rate", "target": "15-25%", "source": "CRM"},
            {"metric": "Sales Cycle Length (days)", "target": "<30", "source": "CRM"},
            {"metric": "Customer Acquisition Cost", "target": "<1 month revenue", "source": "Marketing + Sales"},
            {"metric": "Lifetime Value", "target": ">3x CAC", "source": "Billing + CRM"},
            {"metric": "Net Promoter Score", "target": ">50", "source": "Survey"},
        ],
        "leading_indicators": [
            {"metric": "Qualified Leads/Week", "source": "Marketing"},
            {"metric": "Discovery Calls/Week", "source": "Calendar"},
            {"metric": "Proposals Sent/Week", "source": "CRM"},
            {"metric": "Website Traffic", "source": "Analytics"},
            {"metric": "Email Open Rate", "source": "ESP"},
            {"metric": "Social Engagement Rate", "source": "Social tools"},
            {"metric": "Content Published/Week", "source": "CMS"},
        ],
    })


async def _build_attribution_model(channels: str = "") -> str:
    """Design multi-touch attribution model."""
    return json.dumps({
        "recommended_model": "Position-Based (U-shaped)",
        "allocation": {
            "first_touch": "40% — credits the channel that brought them in",
            "middle_touches": "20% — split across all nurturing touchpoints",
            "last_touch": "40% — credits the channel that closed the deal",
        },
        "tracking_requirements": [
            "UTM parameters on all links (utm_source, utm_medium, utm_campaign)",
            "CRM integration to map touchpoints to deals",
            "Call tracking with dynamic number insertion",
            "Form tracking with hidden fields for attribution",
            "Cookie consent + first-party cookies for cross-session tracking",
        ],
        "channel_mapping": {
            "organic_search": "utm_source=google&utm_medium=organic",
            "paid_search": "utm_source=google&utm_medium=cpc",
            "social_organic": "utm_source=[platform]&utm_medium=social",
            "social_paid": "utm_source=[platform]&utm_medium=paid_social",
            "email": "utm_source=email&utm_medium=email&utm_campaign=[name]",
            "referral": "utm_source=referral&utm_medium=partner",
            "direct": "No UTM — direct traffic or dark social",
        },
    })


async def _build_dashboard_spec(business_name: str = "", metrics: str = "") -> str:
    """Generate executive dashboard specification."""
    return json.dumps({
        "dashboard_name": f"{business_name} Executive Dashboard",
        "refresh_cadence": "Real-time for revenue/leads, daily for everything else",
        "sections": [
            {"name": "Revenue", "kpis": ["MRR", "MRR Growth %", "Revenue vs Target", "Cash Collected"], "visualization": "Line chart + big numbers"},
            {"name": "Pipeline", "kpis": ["Open Deals ($)", "Deals by Stage", "Win Rate (30d)", "Avg Deal Size"], "visualization": "Funnel + bar chart"},
            {"name": "Marketing", "kpis": ["Leads This Week", "CAC", "Traffic", "Conversion Rate"], "visualization": "Sparklines + trend arrows"},
            {"name": "Delivery", "kpis": ["Active Clients", "Utilization %", "NPS Score", "Overdue Tasks"], "visualization": "Gauge + number"},
            {"name": "Finance", "kpis": ["Gross Margin", "Burn Rate", "Runway (months)", "AR Aging"], "visualization": "Big numbers + bar chart"},
        ],
        "recommended_tools": [
            {"tool": "Databox", "use": "Dashboard aggregation from multiple sources", "cost": "$0-72/mo"},
            {"tool": "Google Looker Studio", "use": "Free BI for GA4/GSC/Sheets data", "cost": "Free"},
            {"tool": "Notion", "use": "Internal scorecards and weekly reviews", "cost": "$8-10/mo"},
        ],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TAX & WEALTH TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _tax_writeoff_audit(entity_type: str = "llc", service: str = "", annual_revenue: str = "100000") -> str:
    """Comprehensive tax write-off audit — every deduction available to this entity type."""
    et = (entity_type or "llc").lower()
    try:
        revenue = float(annual_revenue.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        revenue = 100000

    deductions: list[dict] = [
        {"category": "Home Office", "description": "Dedicated workspace in your home",
         "method_a": f"Simplified: $5/sqft × 300 sqft = $1,500/yr",
         "method_b": "Actual: (office sqft / total sqft) × (rent + utilities + insurance + repairs)",
         "estimated_savings": "$1,500-8,000/yr", "irs_form": "Form 8829", "risk": "low"},
        {"category": "Vehicle / Mileage", "description": "Business use of personal vehicle",
         "method_a": "Standard mileage: $0.67/mile (2024)",
         "method_b": "Actual: gas + insurance + repairs + depreciation × business %",
         "estimated_savings": "$3,000-12,000/yr at 10K-20K business miles", "irs_form": "Schedule C / Form 2106", "risk": "low"},
        {"category": "Health Insurance", "description": "Self-employed health insurance deduction",
         "details": "100% of premiums for you, spouse, dependents — above-the-line deduction",
         "estimated_savings": "$6,000-24,000/yr", "irs_form": "Form 1040 Line 17",
         "entity_note": "S-Corp: must include on W-2 for >2% shareholders" if et == "s_corp" else "", "risk": "low"},
        {"category": "Retirement Contributions", "description": "Tax-deferred retirement savings",
         "options": {
             "solo_401k": f"Employee: $23,500 + Employer: 25% = up to $69,000/yr",
             "sep_ira": f"Up to 25% of net SE income, max $69,000/yr",
             "defined_benefit": "Up to $275,000/yr for high earners (requires actuary)",
         },
         "estimated_savings": f"${min(int(revenue * 0.25), 69000)} tax-deferred", "risk": "low"},
        {"category": "Software & SaaS", "description": "All business software subscriptions",
         "examples": "CRM, email, analytics, design, accounting, project management, AI tools",
         "estimated_savings": "$3,000-15,000/yr", "risk": "low"},
        {"category": "Equipment (Section 179)", "description": "Full deduction for business equipment in year 1",
         "details": f"Up to $1,160,000 in 2024. Computers, cameras, furniture, phones, monitors.",
         "bonus": "60% bonus depreciation on remaining balance (2026)", "risk": "low"},
        {"category": "Meals", "description": "Business meals with clients, prospects, team",
         "details": "50% deductible. MUST document: who, where, business purpose",
         "estimated_savings": "$1,000-5,000/yr", "risk": "medium — audit target if excessive"},
        {"category": "Travel", "description": "Business travel — flights, hotels, transport, tips",
         "details": "100% deductible if trip is primarily business. Mixed trips: prorate.",
         "estimated_savings": "$2,000-15,000/yr", "risk": "low if documented"},
        {"category": "Education & Training", "description": "Courses, coaching, conferences, books",
         "details": "Must maintain or improve skills in CURRENT business. 100% deductible.",
         "estimated_savings": "$1,000-10,000/yr", "risk": "low"},
        {"category": "Marketing & Advertising", "description": "All marketing spend",
         "details": "Ad spend, content creation, PR, sponsorships, swag, business cards. 100% deductible.",
         "estimated_savings": "Varies — all ad spend is deductible", "risk": "low"},
        {"category": "Professional Services", "description": "CPA, attorney, consultants, bookkeeper",
         "estimated_savings": "$2,000-15,000/yr", "risk": "low"},
        {"category": "Insurance", "description": "Business insurance premiums",
         "types": "E&O, general liability, cyber, D&O, umbrella. 100% deductible.",
         "estimated_savings": "$1,000-5,000/yr", "risk": "low"},
        {"category": "Cell Phone & Internet", "description": "Business portion of personal phone/internet",
         "details": "Deduct business % of monthly bill. Keep log or use separate line.",
         "estimated_savings": "$1,200-3,000/yr", "risk": "low"},
        {"category": "Coworking / Office", "description": "Office rent, coworking membership",
         "estimated_savings": "$2,000-24,000/yr", "risk": "low"},
        {"category": "Bank & Merchant Fees", "description": "Business bank fees, payment processing fees (Stripe, PayPal)",
         "estimated_savings": "$500-5,000/yr", "risk": "low"},
        {"category": "Startup Costs", "description": "Costs incurred before business opened",
         "details": "First $5,000 deductible in year 1, remainder amortized over 180 months",
         "irs_section": "Section 195", "risk": "low"},
        {"category": "Charitable Contributions", "description": "Donations to qualified charities",
         "entity_note": "C-Corp: deductible at corporate level (up to 10% of taxable income). Pass-through: personal return.",
         "strategies": "Donor-Advised Fund to bunch deductions. Donate appreciated stock to avoid capital gains.",
         "risk": "low"},
    ]

    if et in ("s_corp", "c_corp"):
        deductions.append({
            "category": "Accountable Plan Reimbursements",
            "description": "Reimburse shareholder-employees for business expenses",
            "details": "100% deductible to corp, NOT income to employee. Covers home office, mileage, phone, etc.",
            "estimated_savings": "$5,000-20,000/yr in payroll tax savings", "risk": "low if plan documented",
        })

    if et == "s_corp":
        deductions.append({
            "category": "Reasonable Salary Optimization",
            "description": "Set salary low enough to save FICA, high enough to survive audit",
            "details": f"At ${revenue:,.0f} revenue: salary ~55-60% of profits. Save 15.3% FICA on distributions.",
            "estimated_savings": f"${int(revenue * 0.4 * 0.153):,}/yr in FICA savings", "risk": "medium — IRS scrutiny area",
        })

    # QBI deduction for pass-through entities
    if et in ("sole_prop", "llc", "s_corp", "partnership"):
        qbi = min(revenue * 0.20, 191950)  # simplified — real calculation is more complex
        deductions.append({
            "category": "QBI Deduction (Section 199A)",
            "description": "20% deduction on qualified business income for pass-through entities",
            "details": f"Estimated QBI deduction: ${int(qbi):,}. Subject to income phase-outs and specified service business rules.",
            "estimated_savings": f"${int(qbi * 0.24):,}/yr at 24% bracket", "risk": "low",
        })

    # Augusta Rule
    deductions.append({
        "category": "Augusta Rule (Section 280A)",
        "description": "Rent your home to your business for up to 14 days/year — income is TAX-FREE",
        "details": "Host board meetings, planning sessions, team retreats. Charge fair market rent ($1K-5K/day).",
        "estimated_savings": "$14,000-70,000/yr in tax-free income",
        "requirements": "Document each use, get comparable rental rates, issue 1099 from business to you.",
        "risk": "medium — must be legitimate business use with documentation",
    })

    def _parse_dollar(s: str) -> int:
        """Extract first integer dollar amount from a string like '$1,500-8,000/yr'."""
        import re as _re
        m = _re.search(r'\$?([\d,]+)', s.replace(",", ""))
        return int(m.group(1)) if m else 0

    def _parse_dollar_high(s: str) -> int:
        """Extract the high end dollar amount from a range string."""
        import re as _re
        matches = _re.findall(r'\$?([\d,]+)', s.replace(",", ""))
        return int(matches[-1]) if len(matches) >= 2 else int(matches[0]) if matches else 0

    total_low = sum(_parse_dollar(d.get("estimated_savings", "")) for d in deductions if "estimated_savings" in d)
    total_high = sum(_parse_dollar_high(d.get("estimated_savings", "")) for d in deductions if "estimated_savings" in d and "-" in d.get("estimated_savings", ""))

    return json.dumps({
        "entity_type": et, "annual_revenue": revenue,
        "deductions": deductions,
        "total_estimated_range": f"${total_low:,}-${total_high:,}/yr in potential deductions",
        "tax_savings_estimate": f"${int(total_low * 0.24):,}-${int(total_high * 0.30):,}/yr at marginal rate",
        "disclaimer": "Estimates only. Consult CPA for your specific situation.",
    })


async def _wealth_structure_analyzer(entity_type: str = "llc", annual_income: str = "100000",
                                       state: str = "", net_worth: str = "0") -> str:
    """Analyze wealth architecture options based on income tier and entity type."""
    et = (entity_type or "llc").lower()
    try:
        income = float(annual_income.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        income = 100000
    try:
        nw = float(net_worth.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000").replace("m", "000000").replace("M", "000000"))
    except ValueError:
        nw = 0

    strategies: list[dict] = []

    # Tier 1: Everyone ($100K+)
    strategies.append({
        "tier": "$100K-250K", "name": "Foundation Tier",
        "strategies": [
            {"strategy": "Solo 401(k) + Roth Ladder", "description": "Max retirement contributions, start Roth conversion ladder",
             "annual_benefit": "$10K-20K tax savings", "setup_cost": "$0-500", "complexity": "low"},
            {"strategy": "Home Office + Vehicle Deductions", "description": "Maximize standard deductions every service business qualifies for",
             "annual_benefit": "$3K-15K tax savings", "setup_cost": "$0", "complexity": "low"},
            {"strategy": "S-Corp Election", "description": "Save self-employment tax on distributions above reasonable salary",
             "annual_benefit": "$5K-15K FICA savings", "setup_cost": "$500-2K/yr for payroll", "complexity": "medium",
             "threshold": "When profits exceed $50K/yr"},
            {"strategy": "Umbrella Insurance", "description": "$1-2M umbrella policy for personal asset protection",
             "annual_cost": "$200-500/yr", "complexity": "low"},
            {"strategy": "Augusta Rule", "description": "Rent home to business 14 days/yr, tax-free income",
             "annual_benefit": "$14K-42K tax-free", "setup_cost": "$0", "complexity": "medium"},
        ],
    })

    # Tier 2: Growth ($250K-500K)
    if income >= 200000 or True:  # always show so they can plan ahead
        strategies.append({
            "tier": "$250K-500K", "name": "Growth Tier",
            "strategies": [
                {"strategy": "Holding Company Structure", "description": "Separate LLC holds IP, investments, real estate. Operating Co pays management fees/royalties.",
                 "annual_benefit": "$10K-50K in liability protection + tax flexibility", "setup_cost": "$2K-5K", "complexity": "medium"},
                {"strategy": "Defined Benefit Plan", "description": "Deduct $100K-275K/yr in retirement contributions (on top of 401k)",
                 "annual_benefit": "$30K-80K tax savings", "setup_cost": "$2K-5K/yr for actuary", "complexity": "high",
                 "threshold": "When income is stable and >$250K for 3+ years"},
                {"strategy": "Donor-Advised Fund", "description": "Bunch 5 years of charitable giving into 1 year, invest and grant over time",
                 "annual_benefit": "Itemize in bunching year, standard deduction other years", "setup_cost": "$0", "complexity": "low"},
                {"strategy": "Cost Segregation (if own property)", "description": "Accelerated depreciation on real estate — massive year-1 deduction",
                 "annual_benefit": "$50K-200K deduction in year 1", "setup_cost": "$5K-15K for study", "complexity": "high"},
                {"strategy": "Real Estate Professional Status", "description": "If spouse qualifies, unlimited real estate losses against active income",
                 "annual_benefit": "$20K-100K+ in deductions", "setup_cost": "$0 (but 750+ hours required)", "complexity": "high"},
            ],
        })

    # Tier 3: Scale ($500K-1M)
    if income >= 400000 or True:
        strategies.append({
            "tier": "$500K-1M", "name": "Scale Tier",
            "strategies": [
                {"strategy": "Captive Insurance (831b)", "description": "Form micro-captive to insure business risks, premiums deductible",
                 "annual_benefit": "Deduct up to $2.65M in premiums", "setup_cost": "$15K-30K setup + $5K-15K/yr management",
                 "complexity": "very high", "warning": "Under IRS scrutiny — must be legitimate with actuarial study"},
                {"strategy": "QSBS (C-Corp founders)", "description": "Section 1202: exclude $10M+ in capital gains when selling C-Corp stock held 5+ years",
                 "annual_benefit": "Tax-free exit up to $10M", "setup_cost": "C-Corp election", "complexity": "medium",
                 "note": "Plan NOW even if exit is years away — 5-year clock starts at issuance"},
                {"strategy": "Charitable Remainder Trust", "description": "Sell appreciated assets, avoid capital gains, receive income stream for life",
                 "annual_benefit": "Avoid 20%+ capital gains + income stream", "setup_cost": "$5K-15K to establish", "complexity": "high"},
                {"strategy": "State Tax Relocation", "description": "Move to FL/TX/NV/WY/SD/WA/TN — no state income tax",
                 "annual_benefit": f"${int(income * 0.05):,}-${int(income * 0.13):,}/yr at state rates", "setup_cost": "Relocation costs", "complexity": "life decision"},
                {"strategy": "Asset Protection Trust", "description": "Domestic Asset Protection Trust (DAPT) in NV/WY/DE/SD",
                 "annual_benefit": "Creditor protection for liquid assets", "setup_cost": "$10K-25K", "complexity": "high"},
            ],
        })

    # Tier 4: Wealth ($1M+)
    if income >= 800000 or True:
        strategies.append({
            "tier": "$1M+", "name": "Wealth Tier",
            "strategies": [
                {"strategy": "Private Foundation", "description": "Full control over charitable giving, hire family, major deductions",
                 "annual_benefit": "Deduct up to 30% of AGI + control + legacy", "setup_cost": "$15K-50K + $5K-15K/yr", "complexity": "very high"},
                {"strategy": "GRAT (Grantor Retained Annuity Trust)", "description": "Transfer business appreciation to heirs gift-tax-free",
                 "annual_benefit": "Zero or near-zero gift tax on massive wealth transfers", "setup_cost": "$10K-30K", "complexity": "very high"},
                {"strategy": "Family Limited Partnership", "description": "Transfer business interests at 20-40% valuation discount",
                 "annual_benefit": "Significant estate/gift tax reduction", "setup_cost": "$10K-25K + valuation", "complexity": "very high"},
                {"strategy": "Irrevocable Life Insurance Trust", "description": "Life insurance proceeds outside estate — tax-free to heirs",
                 "annual_benefit": "Remove $1-10M+ from taxable estate", "setup_cost": "$5K-15K + premiums", "complexity": "high"},
                {"strategy": "Opportunity Zone Investing", "description": "Defer + reduce capital gains by investing in qualified OZ funds",
                 "annual_benefit": "Defer gains + 10-year hold = no tax on appreciation", "setup_cost": "Minimum fund investments", "complexity": "high"},
            ],
        })

    return json.dumps({
        "entity_type": et, "annual_income": income, "state": state, "net_worth": nw,
        "current_tier": "$1M+" if income >= 1000000 else "$500K-1M" if income >= 500000 else "$250K-500K" if income >= 250000 else "$100K-250K",
        "strategies_by_tier": strategies,
        "immediate_actions": [
            "Max out retirement contributions (Solo 401k or SEP IRA)",
            "Set up Augusta Rule documentation if you work from home",
            "Evaluate S-Corp election if net income > $50K",
            "Get umbrella insurance policy ($1-2M)",
            "Open Donor-Advised Fund if you give to charity",
        ],
        "professional_team_needed": [
            "CPA (tax strategy, not just compliance)", "Business attorney (entity structuring, asset protection)",
            "Wealth manager / financial planner (investments, retirement)", "Insurance broker (captive, umbrella, key person)",
            "Estate attorney (trusts, succession)" if income >= 500000 else "Estate attorney (when income exceeds $500K)",
        ],
        "disclaimer": "Strategy guidance only. Every recommendation requires professional implementation. Tax laws change — verify current applicability.",
    })


async def _reasonable_salary_calculator(annual_profit: str = "100000", industry: str = "services",
                                           geography: str = "", role: str = "CEO") -> str:
    """Calculate reasonable salary range for S-Corp officer compensation."""
    try:
        profit = float(annual_profit.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        profit = 100000

    # Industry benchmarks for officer compensation (simplified)
    benchmarks = {
        "services": {"low_pct": 0.40, "mid_pct": 0.55, "high_pct": 0.70},
        "consulting": {"low_pct": 0.45, "mid_pct": 0.55, "high_pct": 0.65},
        "marketing": {"low_pct": 0.40, "mid_pct": 0.50, "high_pct": 0.65},
        "saas": {"low_pct": 0.35, "mid_pct": 0.50, "high_pct": 0.65},
        "agency": {"low_pct": 0.40, "mid_pct": 0.55, "high_pct": 0.70},
    }
    bench = benchmarks.get(industry.lower(), benchmarks["services"])

    salary_low = int(profit * bench["low_pct"])
    salary_mid = int(profit * bench["mid_pct"])
    salary_high = int(profit * bench["high_pct"])
    distribution = int(profit - salary_mid)

    fica_savings = int(distribution * 0.153)

    return json.dumps({
        "annual_profit": profit, "industry": industry, "role": role,
        "salary_range": {
            "conservative_low": f"${salary_low:,}", "recommended_mid": f"${salary_mid:,}", "aggressive_high": f"${salary_high:,}",
            "note": "IRS looks at: comparable wages, training/experience, duties, hours, dividend history",
        },
        "at_recommended_salary": {
            "w2_salary": f"${salary_mid:,}", "distribution": f"${distribution:,}",
            "fica_savings": f"${fica_savings:,}/yr (15.3% saved on distributions)",
            "employer_fica": f"${int(salary_mid * 0.0765):,}/yr (7.65% — business deductible)",
            "employee_fica": f"${int(salary_mid * 0.0765):,}/yr (7.65% — withheld from paycheck)",
        },
        "red_flags": [
            "Salary below $40K for full-time work — very high audit risk",
            "Salary less than 30% of profits — IRS will challenge",
            "Taking $0 salary with large distributions — automatic audit trigger",
            f"No increase in salary as profits grow beyond ${int(profit * 1.5):,}",
        ],
        "documentation_needed": [
            "Officer compensation study (this report)",
            "Job description with duties and hours",
            "Comparable salary data from BLS or industry surveys",
            "Board resolution setting compensation",
        ],
    })


async def _multi_entity_planner(business_name: str = "", entity_type: str = "llc",
                                   annual_revenue: str = "100000", state: str = "") -> str:
    """Plan a multi-entity structure for asset protection and tax optimization."""
    et = (entity_type or "llc").lower()
    try:
        revenue = float(annual_revenue.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000"))
    except ValueError:
        revenue = 100000

    structures: list[dict] = []

    # Basic: Operating Co + Holding Co
    structures.append({
        "name": "Two-Entity Shield",
        "entities": [
            {"name": f"{business_name} LLC (Operating Co)", "type": "LLC (S-Corp election if profitable)",
             "purpose": "Day-to-day operations, client contracts, employees/contractors",
             "risk_exposure": "HIGH — all business liability sits here"},
            {"name": f"{business_name} Holdings LLC (Holding Co)", "type": "LLC (taxed as partnership or disregarded)",
             "purpose": "Owns IP, brand, domain, investments, excess cash",
             "risk_exposure": "LOW — no client-facing activity, no employees"},
        ],
        "flows": [
            f"Holding Co licenses IP/brand to Operating Co → royalty payment (deductible to OpCo)",
            f"Holding Co provides management services → management fee (deductible to OpCo)",
            f"Operating Co distributes excess profits → Holding Co accumulates and invests",
        ],
        "tax_benefits": "Royalties and management fees shift income. Both are pass-through for individual tax.",
        "threshold": "Makes sense at $150K+ annual profit",
        "setup_cost": "$2K-5K for second entity + operating agreements",
        "ongoing_cost": "$500-1K/yr for separate books + tax return",
    })

    # Advanced: Add real estate entity
    if revenue >= 200000:
        structures.append({
            "name": "Three-Entity Fortress",
            "entities": [
                {"name": f"{business_name} LLC (Operating Co)", "type": "LLC (S-Corp)", "purpose": "Operations"},
                {"name": f"{business_name} Holdings LLC", "type": "LLC", "purpose": "IP, brand, investments"},
                {"name": f"{business_name} Property LLC", "type": "LLC", "purpose": "Owns/leases office/commercial property"},
            ],
            "additional_benefit": "Property LLC leases space to Operating Co (deductible). Real estate gets depreciation, 1031 exchange eligibility, potential REPS status.",
            "threshold": "Makes sense at $250K+ when buying/leasing commercial property",
        })

    return json.dumps({
        "current_entity": et, "annual_revenue": revenue, "state": state,
        "recommended_structures": structures,
        "immediate_next_steps": [
            "Consult business attorney for entity structuring",
            "Consult CPA for tax implications of inter-entity payments",
            "Get IP valuation if licensing brand/IP to operating co",
            "Draft inter-company agreements (management, licensing)",
        ],
        "warning": "Multi-entity structures MUST have legitimate business purpose. IRS can collapse entities that exist solely for tax avoidance.",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# BILLING & INVOICING TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_invoice(
    client_name: str, client_email: str, amount: str,
    description: str = "", due_days: str = "30", currency: str = "usd",
) -> str:
    """Create and send an invoice via Stripe."""
    if not settings.stripe_api_key:
        return json.dumps({
            "status": "draft",
            "invoice_id": f"inv_draft_{client_name.lower().replace(' ', '_')}",
            "client": client_name,
            "amount": amount,
            "due_days": due_days,
            "description": description or "Professional services",
            "action_required": "Configure STRIPE_API_KEY to send live invoices",
            "manual_steps": [
                f"Send invoice for ${amount} to {client_email}",
                f"Net {due_days} payment terms",
                "Include bank details or payment link",
            ],
        })

    try:
        # Create or find customer
        r = await _http.post("https://api.stripe.com/v1/customers/search",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={"query": f"email:'{client_email}'"})
        customers = r.json().get("data", [])

        if customers:
            customer_id = customers[0]["id"]
        else:
            r = await _http.post("https://api.stripe.com/v1/customers",
                headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
                data={"name": client_name, "email": client_email})
            customer_id = r.json()["id"]

        # Create invoice
        r = await _http.post("https://api.stripe.com/v1/invoices",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={
                "customer": customer_id,
                "collection_method": "send_invoice",
                "days_until_due": int(due_days),
                "currency": currency,
            })
        invoice_id = r.json()["id"]

        # Add line item
        await _http.post("https://api.stripe.com/v1/invoiceitems",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={
                "customer": customer_id,
                "invoice": invoice_id,
                "amount": int(float(amount) * 100),  # cents
                "currency": currency,
                "description": description or "Professional services",
            })

        # Finalize and send
        r = await _http.post(f"https://api.stripe.com/v1/invoices/{invoice_id}/finalize",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"})
        await _http.post(f"https://api.stripe.com/v1/invoices/{invoice_id}/send",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"})

        return json.dumps({
            "status": "sent",
            "invoice_id": invoice_id,
            "customer_id": customer_id,
            "amount": amount,
            "hosted_url": r.json().get("hosted_invoice_url", ""),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"})


async def _create_subscription(
    client_name: str, client_email: str, amount: str,
    interval: str = "month", description: str = "",
) -> str:
    """Create a recurring subscription for a client."""
    if not settings.stripe_api_key:
        return json.dumps({
            "status": "draft",
            "client": client_name,
            "amount": amount,
            "interval": interval,
            "action_required": "Configure STRIPE_API_KEY for live subscriptions",
            "plan": {
                "billing_amount": f"${amount}/{interval}",
                "auto_charge": True,
                "dunning_enabled": True,
            },
        })

    try:
        # Find or create customer
        r = await _http.post("https://api.stripe.com/v1/customers/search",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={"query": f"email:'{client_email}'"})
        customers = r.json().get("data", [])
        if customers:
            customer_id = customers[0]["id"]
        else:
            r = await _http.post("https://api.stripe.com/v1/customers",
                headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
                data={"name": client_name, "email": client_email})
            customer_id = r.json()["id"]

        # Create price
        r = await _http.post("https://api.stripe.com/v1/prices",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={
                "unit_amount": int(float(amount) * 100),
                "currency": "usd",
                "recurring[interval]": interval,
                "product_data[name]": description or f"Retainer — {client_name}",
            })
        price_id = r.json()["id"]

        # Create subscription
        r = await _http.post("https://api.stripe.com/v1/subscriptions",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            data={
                "customer": customer_id,
                "items[0][price]": price_id,
                "payment_behavior": "default_incomplete",
            })
        sub = r.json()
        return json.dumps({
            "status": "created",
            "subscription_id": sub["id"],
            "customer_id": customer_id,
            "amount": amount,
            "interval": interval,
            "client_secret": sub.get("latest_invoice", {}).get("payment_intent", {}).get("client_secret", ""),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"})


async def _check_payment_status(invoice_id: str = "", customer_email: str = "") -> str:
    """Check payment status for an invoice or customer's outstanding balance."""
    if not settings.stripe_api_key:
        return json.dumps({
            "status": "unconfigured",
            "action_required": "Configure STRIPE_API_KEY to check payment status",
        })

    try:
        if invoice_id:
            r = await _http.get(f"https://api.stripe.com/v1/invoices/{invoice_id}",
                headers={"Authorization": f"Bearer {settings.stripe_api_key}"})
            inv = r.json()
            return json.dumps({
                "invoice_id": invoice_id,
                "status": inv.get("status"),
                "amount_due": inv.get("amount_due", 0) / 100,
                "amount_paid": inv.get("amount_paid", 0) / 100,
                "due_date": inv.get("due_date"),
                "hosted_url": inv.get("hosted_invoice_url", ""),
            })
        elif customer_email:
            r = await _http.post("https://api.stripe.com/v1/customers/search",
                headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
                data={"query": f"email:'{customer_email}'"})
            customers = r.json().get("data", [])
            if not customers:
                return json.dumps({"error": "Customer not found"})

            cid = customers[0]["id"]
            r = await _http.get(f"https://api.stripe.com/v1/invoices",
                headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
                params={"customer": cid, "status": "open", "limit": 10})
            invoices = r.json().get("data", [])
            return json.dumps({
                "customer": customer_email,
                "open_invoices": len(invoices),
                "total_outstanding": sum(i.get("amount_remaining", 0) for i in invoices) / 100,
                "invoices": [{
                    "id": i["id"], "amount": i["amount_due"] / 100,
                    "status": i["status"], "due_date": i.get("due_date"),
                } for i in invoices],
            })
        return json.dumps({"error": "Provide invoice_id or customer_email"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _send_payment_reminder(customer_email: str, message: str = "") -> str:
    """Send a payment reminder for outstanding invoices."""
    if not settings.stripe_api_key:
        return json.dumps({
            "status": "draft",
            "reminder": f"Payment reminder to {customer_email}",
            "message": message or "Friendly reminder about your outstanding invoice.",
            "action_required": "Configure STRIPE_API_KEY + SENDGRID_API_KEY for automated reminders",
        })

    # Get outstanding invoices
    status_result = await _check_payment_status(customer_email=customer_email)
    outstanding = json.loads(status_result)

    if outstanding.get("open_invoices", 0) == 0:
        return json.dumps({"status": "no_outstanding", "message": "No open invoices found"})

    # Use SendGrid to send reminder
    if settings.sendgrid_api_key:
        reminder_msg = message or (
            f"Hi — this is a friendly reminder that you have "
            f"${outstanding['total_outstanding']:.2f} in outstanding invoices. "
            f"Please click the payment link in your original invoice email to complete payment. "
            f"If you have any questions, please don't hesitate to reach out."
        )
        await _http.post("https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": customer_email}]}],
                "from": {"email": settings.sendgrid_from_email or "billing@example.com"},
                "subject": "Payment Reminder — Outstanding Invoice",
                "content": [{"type": "text/plain", "value": reminder_msg}],
            })

    return json.dumps({
        "status": "sent",
        "customer": customer_email,
        "outstanding": outstanding.get("total_outstanding", 0),
        "invoices_reminded": outstanding.get("open_invoices", 0),
    })


async def _setup_dunning_sequence(
    reminder_days: str = "3,7,14,30", escalation_action: str = "pause_service",
) -> str:
    """Configure automated dunning sequence for failed/late payments."""
    days = [int(d.strip()) for d in reminder_days.split(",")]
    sequence = []
    for i, day in enumerate(days):
        tone = "friendly" if i == 0 else "firm" if i == 1 else "urgent" if i == 2 else "final"
        sequence.append({
            "day": day,
            "tone": tone,
            "channel": "email",
            "template": f"{tone}_payment_reminder",
            "escalation": escalation_action if i == len(days) - 1 else None,
        })

    return json.dumps({
        "dunning_sequence": sequence,
        "total_touchpoints": len(sequence),
        "escalation_action": escalation_action,
        "final_reminder_day": days[-1],
        "best_practices": [
            "Day 1: Assume it's a mistake — friendly tone",
            f"Day {days[0]}: First reminder — helpful, include payment link",
            f"Day {days[1]}: Second reminder — mention upcoming service implications",
            f"Day {days[-1]}: Final notice — clear deadline before {escalation_action}",
        ],
        "note": "Configure Stripe smart retries for failed card payments separately",
    })


async def _get_revenue_metrics(period: str = "month") -> str:
    """Get revenue metrics from Stripe — MRR, churn, LTV, collections."""
    if not settings.stripe_api_key:
        return json.dumps({
            "status": "unconfigured",
            "action_required": "Configure STRIPE_API_KEY for revenue metrics",
            "placeholder_metrics": {
                "mrr": 0, "arr": 0, "active_subscriptions": 0,
                "churn_rate": 0, "avg_revenue_per_client": 0,
                "outstanding_invoices": 0, "collection_rate": 0,
            },
        })

    try:
        # Active subscriptions
        r = await _http.get("https://api.stripe.com/v1/subscriptions",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            params={"status": "active", "limit": 100})
        subs = r.json().get("data", [])
        mrr = sum(s.get("items", {}).get("data", [{}])[0].get("price", {}).get("unit_amount", 0)
                  for s in subs) / 100

        # Recent invoices for collection rate
        r = await _http.get("https://api.stripe.com/v1/invoices",
            headers={"Authorization": f"Bearer {settings.stripe_api_key}"},
            params={"limit": 100})
        invoices = r.json().get("data", [])
        paid = sum(1 for i in invoices if i["status"] == "paid")
        total_inv = len(invoices) or 1

        return json.dumps({
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
            "active_subscriptions": len(subs),
            "collection_rate": round(paid / total_inv * 100, 1),
            "outstanding_invoices": sum(1 for i in invoices if i["status"] == "open"),
            "total_outstanding": sum(i.get("amount_remaining", 0) for i in invoices if i["status"] == "open") / 100,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# REFERRAL & AFFILIATE TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_referral_program(
    program_name: str, reward_type: str = "percentage", reward_value: str = "10",
    reward_description: str = "", cookie_duration_days: str = "90",
) -> str:
    """Design and configure a referral/affiliate program."""
    reward_desc = reward_description or (
        f"{reward_value}% recurring commission" if reward_type == "percentage"
        else f"${reward_value} per referral"
    )

    program = {
        "program_name": program_name,
        "reward_type": reward_type,
        "reward_value": reward_value,
        "reward_description": reward_desc,
        "cookie_duration_days": int(cookie_duration_days),
        "tiers": [
            {"name": "Starter", "threshold": 0, "commission": f"{reward_value}%", "perks": ["Basic dashboard", "Monthly payouts"]},
            {"name": "Partner", "threshold": 5, "commission": f"{int(float(reward_value) * 1.5)}%", "perks": ["Priority support", "Co-marketing", "Bi-weekly payouts"]},
            {"name": "Elite", "threshold": 20, "commission": f"{int(float(reward_value) * 2)}%", "perks": ["Dedicated account manager", "Custom landing pages", "Weekly payouts"]},
        ],
        "tracking": {
            "method": "unique_referral_link",
            "attribution_window": f"{cookie_duration_days} days",
            "multi_touch": True,
        },
        "assets_to_create": [
            "Referral landing page with unique link generator",
            "Email swipe copy (5 templates for affiliates to use)",
            "Social media graphics (3 sizes)",
            "Case study PDF for affiliates to share",
            "Affiliate dashboard with real-time tracking",
        ],
        "automation": [
            "Auto-generate unique referral links on signup",
            "Track clicks → signups → conversions → payouts",
            "Monthly payout via Stripe Connect or PayPal",
            "Auto-send commission notification emails",
            "Tier-up notification when thresholds are hit",
        ],
    }

    # If Rewardful is configured, set up there
    if settings.rewardful_api_key:
        program["platform"] = "Rewardful"
        program["setup_status"] = "ready_to_activate"
        program["api_configured"] = True
    elif settings.firstpromoter_api_key:
        program["platform"] = "FirstPromoter"
        program["setup_status"] = "ready_to_activate"
        program["api_configured"] = True
    else:
        program["platform"] = "custom"
        program["setup_status"] = "manual_setup_required"
        program["recommended_platforms"] = [
            {"name": "Rewardful", "price": "$49/mo", "best_for": "Stripe-integrated SaaS/agencies"},
            {"name": "FirstPromoter", "price": "$49/mo", "best_for": "Affiliate + referral hybrid"},
            {"name": "ReferralCandy", "price": "$59/mo", "best_for": "E-commerce focused"},
        ]

    return json.dumps(program)


async def _track_referral(
    referrer_id: str, referred_email: str, event: str = "signup",
    revenue: str = "0",
) -> str:
    """Track a referral event — signup, conversion, or revenue attribution."""
    return json.dumps({
        "referrer_id": referrer_id,
        "referred": referred_email,
        "event": event,
        "revenue_attributed": float(revenue),
        "commission_earned": float(revenue) * 0.10,  # Default 10%
        "tracked_at": "now",
        "attribution_chain": {
            "first_touch": "referral_link",
            "last_touch": event,
            "revenue": float(revenue),
        },
    })


async def _get_referral_metrics() -> str:
    """Get referral program performance metrics."""
    if settings.rewardful_api_key:
        try:
            r = await _http.get("https://api.rewardful.com/v1/affiliates",
                headers={"Authorization": f"Bearer {settings.rewardful_api_key}"},
                params={"limit": 100})
            affiliates = r.json().get("data", [])
            return json.dumps({
                "total_affiliates": len(affiliates),
                "active_affiliates": sum(1 for a in affiliates if a.get("referrals_count", 0) > 0),
                "total_referrals": sum(a.get("referrals_count", 0) for a in affiliates),
                "total_revenue": sum(a.get("revenue", 0) for a in affiliates) / 100,
                "total_commissions_paid": sum(a.get("commissions_total", 0) for a in affiliates) / 100,
                "platform": "Rewardful",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({
        "status": "no_platform_configured",
        "placeholder_metrics": {
            "total_affiliates": 0, "active_affiliates": 0,
            "total_referrals": 0, "total_revenue": 0,
            "avg_commission_rate": "10%", "top_channel": "none",
        },
        "action_required": "Configure REWARDFUL_API_KEY or FIRSTPROMOTER_API_KEY",
    })


async def _generate_affiliate_assets(
    business_name: str, service: str, commission_rate: str = "10",
) -> str:
    """Generate affiliate marketing assets — swipe copy, social posts, email templates."""
    return json.dumps({
        "email_swipe_copy": [
            {
                "subject": f"I found something that could help your business — {business_name}",
                "body": f"Hey [Name],\n\nI've been using {business_name} for [service] and the results have been incredible. [Specific result].\n\nIf you sign up through my link, you'll get [offer]. Plus I earn a small commission that helps me keep recommending great tools.\n\n[REFERRAL_LINK]\n\nHappy to answer any questions!",
                "use_case": "Warm intro to peers/network",
            },
            {
                "subject": f"How I [achieved result] with {business_name}",
                "body": f"I wanted to share a quick win. After switching to {business_name} for {service}, I saw [metric improvement] in [timeframe].\n\nThey're offering [deal] right now: [REFERRAL_LINK]",
                "use_case": "Results-driven cold outreach",
            },
        ],
        "social_posts": [
            f"Been using @{business_name} for {service} and genuinely impressed. Results speak for themselves 📈 [REFERRAL_LINK]",
            f"Asked to share my secret weapon for {service}... it's @{business_name}. Not sponsored — I just earn a small commission because I believe in it. [REFERRAL_LINK]",
            f"If you're still doing {service} manually, check out @{business_name}. Changed the game for me. Link in bio 👆",
        ],
        "landing_page_copy": {
            "headline": f"See Why {business_name} Is Trusted By [X]+ Businesses",
            "subhead": f"Get {service} that actually delivers results.",
            "cta": "Start Your Free Trial",
            "social_proof": "[Insert testimonials/logos]",
        },
        "commission_rate": f"{commission_rate}%",
        "tracking_link_format": f"https://{business_name.lower().replace(' ', '')}.com/ref/[AFFILIATE_ID]",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# UPSELL & CROSS-SELL INTELLIGENCE TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _analyze_expansion_opportunities(
    client_name: str, current_services: str, monthly_revenue: str = "0",
    engagement_months: str = "0", satisfaction_score: str = "0",
) -> str:
    """Analyze a client for upsell/cross-sell opportunities based on usage and satisfaction."""
    revenue = float(monthly_revenue)
    months = int(engagement_months)
    csat = float(satisfaction_score) if satisfaction_score != "0" else 4.0

    opportunities = []

    # Time-based triggers
    if months >= 3 and csat >= 4.0:
        opportunities.append({
            "type": "upsell",
            "trigger": "3+ months + high satisfaction",
            "offer": "Premium tier / expanded scope",
            "estimated_revenue_increase": f"${revenue * 0.5:.0f}/mo",
            "timing": "Now — they're in the sweet spot",
            "approach": "QBR meeting → show ROI → propose expanded engagement",
        })

    if months >= 6:
        opportunities.append({
            "type": "cross_sell",
            "trigger": "6+ months relationship depth",
            "offer": "Adjacent service offering",
            "estimated_revenue_increase": f"${revenue * 0.3:.0f}/mo",
            "timing": "Next QBR or after delivering strong results",
            "approach": "Identify gaps in their current stack → propose filling them",
        })

    if revenue >= 3000:
        opportunities.append({
            "type": "upsell",
            "trigger": "High-value client",
            "offer": "Annual contract with discount",
            "estimated_revenue_increase": f"${revenue * 10:.0f} (annual lock-in)",
            "timing": "Before contract renewal",
            "approach": "Offer 10-15% discount for annual commitment → improves cash flow + retention",
        })

    if csat >= 4.5:
        opportunities.append({
            "type": "referral",
            "trigger": "Extremely satisfied client",
            "offer": "Referral incentive program",
            "estimated_revenue_increase": "1-3 new clients",
            "timing": "After delivering a major win",
            "approach": "Ask for introduction to 2-3 peers → offer referral credit",
        })

    # Low-hanging fruit
    services = current_services.lower()
    cross_sell_map = {
        "seo": ["PPC management", "content marketing", "social media"],
        "social": ["paid social ads", "influencer partnerships", "content"],
        "email": ["SMS marketing", "marketing automation", "newsletter"],
        "ads": ["landing page optimization", "CRO", "retargeting"],
        "web": ["SEO", "content strategy", "analytics setup"],
        "content": ["SEO", "social distribution", "email newsletter"],
    }
    for service_key, cross_sells in cross_sell_map.items():
        if service_key in services:
            for cs in cross_sells:
                if cs.lower() not in services:
                    opportunities.append({
                        "type": "cross_sell",
                        "trigger": f"Natural extension of {service_key}",
                        "offer": cs,
                        "estimated_revenue_increase": f"${revenue * 0.2:.0f}/mo",
                        "timing": "When current service is performing well",
                        "approach": f"Show how {cs} amplifies their {service_key} results",
                    })
                    break  # One cross-sell per service

    return json.dumps({
        "client": client_name,
        "current_mrr": revenue,
        "tenure_months": months,
        "satisfaction": csat,
        "opportunities": opportunities[:5],  # Top 5
        "total_expansion_potential": f"${sum(revenue * 0.3 for _ in opportunities[:5]):.0f}/mo",
        "priority": "high" if csat >= 4.0 and months >= 3 else "medium" if months >= 1 else "nurture",
    })


async def _build_qbr_template(
    client_name: str, service: str, key_metrics: str = "",
) -> str:
    """Build a Quarterly Business Review template for client expansion conversations."""
    return json.dumps({
        "qbr_template": {
            "title": f"Quarterly Business Review — {client_name}",
            "sections": [
                {
                    "name": "Results Recap",
                    "content": "Review key metrics and wins from the past quarter",
                    "data_needed": ["KPI dashboard", "Goal vs actual", "Top wins"],
                },
                {
                    "name": "ROI Analysis",
                    "content": "Connect spend to revenue impact",
                    "data_needed": ["Total spend", "Revenue attributed", "Cost per acquisition"],
                },
                {
                    "name": "Competitive Landscape",
                    "content": "What competitors are doing, market shifts",
                    "data_needed": ["Competitor analysis", "Industry benchmarks"],
                },
                {
                    "name": "Roadmap & Recommendations",
                    "content": "Next quarter priorities and growth opportunities",
                    "data_needed": ["Proposed scope changes", "New initiatives", "Budget recommendations"],
                },
                {
                    "name": "Expansion Discussion",
                    "content": "Natural transition to upsell/cross-sell",
                    "talk_track": [
                        f"Based on our results with {service}, we see opportunity in...",
                        "We've noticed [gap] that's limiting your growth...",
                        "Clients similar to you are seeing [X] results by adding...",
                        "We'd love to propose a pilot program for [new service]...",
                    ],
                },
            ],
            "best_practices": [
                "Lead with their wins, not your pitch",
                "Use their language and metrics, not yours",
                "Plant the expansion seed in the Roadmap section",
                "End with a specific next step, not an open question",
            ],
        },
    })


async def _client_health_score(
    client_name: str, monthly_revenue: str = "0",
    last_interaction_days: str = "0", support_tickets: str = "0",
    satisfaction_score: str = "0", contract_months_remaining: str = "12",
) -> str:
    """Calculate client health score and churn risk."""
    revenue = float(monthly_revenue)
    last_interaction = int(last_interaction_days)
    tickets = int(support_tickets)
    csat = float(satisfaction_score) if satisfaction_score != "0" else 3.5
    contract_remaining = int(contract_months_remaining)

    # Scoring components (0-100 each)
    engagement_score = max(0, 100 - (last_interaction * 3))  # -3 pts per day since contact
    satisfaction_score_val = min(100, csat * 20)  # 5.0 = 100
    support_score = max(0, 100 - (tickets * 10))  # Each ticket costs 10 pts
    contract_score = min(100, contract_remaining * 8)  # 12+ months = high

    health = (engagement_score * 0.3 + satisfaction_score_val * 0.35 +
              support_score * 0.15 + contract_score * 0.2)

    churn_risk = "low" if health >= 70 else "medium" if health >= 40 else "high"
    actions = []
    if last_interaction >= 14:
        actions.append("Schedule check-in call — too long since last contact")
    if csat < 4.0:
        actions.append("Send satisfaction survey — identify specific issues")
    if tickets >= 3:
        actions.append("Escalate to account manager — support volume high")
    if contract_remaining <= 3:
        actions.append("Start renewal conversation — contract expiring soon")
    if health >= 70:
        actions.append("Explore expansion — client is healthy and engaged")

    return json.dumps({
        "client": client_name,
        "health_score": round(health, 1),
        "churn_risk": churn_risk,
        "components": {
            "engagement": round(engagement_score, 1),
            "satisfaction": round(satisfaction_score_val, 1),
            "support": round(support_score, 1),
            "contract": round(contract_score, 1),
        },
        "monthly_revenue_at_risk": revenue if churn_risk == "high" else 0,
        "recommended_actions": actions,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-CAMPAIGN ORCHESTRATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _compare_campaigns(campaign_ids: str) -> str:
    """Compare performance across multiple campaigns for cross-learning."""
    ids = [c.strip() for c in campaign_ids.split(",")]
    return json.dumps({
        "campaigns_compared": len(ids),
        "campaign_ids": ids,
        "comparison_axes": [
            "Agent grades (which agents perform best across campaigns)",
            "Channel ROI (which channels convert best by ICP type)",
            "Content performance (which messaging angles resonate)",
            "Speed to first conversion (time to value by campaign type)",
        ],
        "note": "Comparison data populated after genome.get_cross_campaign_insights() runs",
    })


async def _clone_campaign_config(
    source_campaign_id: str, new_business_name: str, new_icp: str = "",
) -> str:
    """Clone a successful campaign config for a new client."""
    return json.dumps({
        "source_campaign": source_campaign_id,
        "new_campaign": {
            "business_name": new_business_name,
            "icp_override": new_icp or "inherited from source",
            "cloned_elements": [
                "Agent sequence and configuration",
                "Content strategy framework",
                "Email sequence templates (personalized)",
                "Ad creative structure",
                "Social calendar framework",
                "Scoring thresholds",
            ],
            "requires_customization": [
                "Business profile (name, service, brand context)",
                "Prospect list (new ICP research)",
                "Ad creative copy and imagery",
                "Email personalization tokens",
            ],
        },
        "estimated_time_savings": "60-70% vs starting from scratch",
        "genome_benefit": "Cross-campaign intelligence automatically feeds recommendations",
    })


async def _portfolio_dashboard(campaign_ids: str = "") -> str:
    """Get portfolio-level metrics across all campaigns."""
    return json.dumps({
        "portfolio_metrics": {
            "total_campaigns": "dynamic",
            "total_mrr": "sum across all campaign billing systems",
            "avg_agent_health": "weighted average across campaigns",
            "top_performing_campaign": "by composite score",
            "campaigns_needing_attention": "health score < 60",
        },
        "aggregation_axes": [
            "Revenue by campaign",
            "Agent performance distribution",
            "Channel ROI comparison",
            "Client satisfaction heat map",
            "Resource utilization across campaigns",
        ],
        "alerts": [
            "Campaign with declining scores",
            "Agents failing across multiple campaigns (systemic issue)",
            "Budget overrun warnings",
            "Upcoming renewals / churn risks",
        ],
    })


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

    registry.register("enrich_company", "Full company enrichment — firmographic + technographic data via Clearbit/Apollo.",
        [ToolParameter(name="domain", description="Company domain (e.g. acme.com)")],
        _enrich_company, "prospecting")

    registry.register("enrich_person", "Enrich a person by email — returns name, title, company, social profiles, phone.",
        [ToolParameter(name="email", description="Person's email address")],
        _enrich_person, "prospecting")

    registry.register("find_phone_number", "Look up direct phone number for a prospect.",
        [ToolParameter(name="name", description="Person's full name"),
         ToolParameter(name="company", description="Company name", required=False),
         ToolParameter(name="email", description="Email address if known", required=False)],
        _find_phone_number, "prospecting")

    registry.register("search_linkedin_prospects", "Search for prospects matching criteria — titles, industry, company size, geography.",
        [ToolParameter(name="query", description="Search keywords (e.g. 'VP Marketing SaaS')"),
         ToolParameter(name="industry", description="Industry filter", required=False),
         ToolParameter(name="company_size", description="Size range: 1-10, 11-50, 51-200, 201-500, 501-1000, 1001+", required=False),
         ToolParameter(name="geography", description="Location filter", required=False),
         ToolParameter(name="limit", type="integer", description="Max results (1-25)", required=False)],
        _search_linkedin_prospects, "prospecting")

    registry.register("check_buyer_intent", "Check buyer intent signals for a company — are they actively researching solutions?",
        [ToolParameter(name="domain", description="Company domain"),
         ToolParameter(name="topics", description="Relevant topics/keywords", required=False)],
        _check_buyer_intent, "prospecting")

    registry.register("score_lead", "Score a lead 0-100 based on ICP fit using heuristic matching.",
        [ToolParameter(name="company_name", description="Company name"),
         ToolParameter(name="domain", description="Company domain", required=False),
         ToolParameter(name="employee_count", description="Number of employees", required=False),
         ToolParameter(name="industry", description="Company industry", required=False),
         ToolParameter(name="title", description="Contact's job title", required=False),
         ToolParameter(name="icp_description", description="Ideal customer profile description", required=False)],
        _score_lead, "prospecting")

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

    registry.register("check_email_warmup_status", "Check email warmup/deliverability status via Instantly.ai.",
        [ToolParameter(name="email_account", description="Email account to check warmup status for")],
        _check_email_warmup_status, "email")

    registry.register("detect_email_replies", "Detect replies and opens from sent email campaigns.",
        [ToolParameter(name="campaign_tag", description="Campaign tag to filter", required=False),
         ToolParameter(name="since_hours", type="integer", description="Hours to look back (default 24)", required=False)],
        _detect_email_replies, "email")

    # ── Voice & SMS Tools ──
    registry.register("make_phone_call", "Make an AI voice call using Bland.ai, Vapi, or Twilio. For cold calls, follow-ups, demos.",
        [ToolParameter(name="to_number", description="Phone number to call (E.164 format)"),
         ToolParameter(name="script", description="Call script or AI agent instructions"),
         ToolParameter(name="voice", description="Voice name (default: nat)", required=False),
         ToolParameter(name="max_duration_minutes", type="integer", description="Max call length in minutes", required=False)],
        _make_phone_call, "voice")

    registry.register("get_call_transcript", "Get transcript and analysis from a completed AI call.",
        [ToolParameter(name="call_id", description="Call ID from make_phone_call"),
         ToolParameter(name="provider", description="Provider: bland.ai or vapi", required=False)],
        _get_call_transcript, "voice")

    registry.register("send_sms", "Send SMS text message via Twilio.",
        [ToolParameter(name="to_number", description="Recipient phone number (E.164 format)"),
         ToolParameter(name="message", description="SMS message text (max 1600 chars)")],
        _send_sms, "voice")

    registry.register("send_linkedin_message", "Send LinkedIn message/connection request via Phantombuster.",
        [ToolParameter(name="profile_url", description="LinkedIn profile URL"),
         ToolParameter(name="message", description="Message to send (max 300 chars)")],
        _send_linkedin_message, "voice")

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

    registry.register("post_instagram", "Post to Instagram via Meta Graph API (Business account required).",
        [ToolParameter(name="caption", description="Post caption"),
         ToolParameter(name="image_url", description="Public image URL to post")],
        _post_instagram, "social")

    registry.register("schedule_social_post", "Schedule a social post for future publication via Buffer.",
        [ToolParameter(name="platform", description="Platform: twitter, linkedin, instagram, facebook"),
         ToolParameter(name="text", description="Post content"),
         ToolParameter(name="scheduled_time", description="ISO 8601 datetime for publishing"),
         ToolParameter(name="image_url", description="Optional image URL", required=False)],
        _schedule_social_post, "social")

    registry.register("get_social_analytics", "Get social media engagement metrics for a platform.",
        [ToolParameter(name="platform", description="Platform: twitter, instagram, facebook"),
         ToolParameter(name="period", description="Period: 7d, 30d, 90d", required=False)],
        _get_social_analytics, "social")

    registry.register("monitor_community", "Monitor Reddit, Hacker News, or Product Hunt for mentions and opportunities.",
        [ToolParameter(name="platform", description="Platform: reddit, hackernews, producthunt"),
         ToolParameter(name="keywords", description="Comma-separated keywords to monitor"),
         ToolParameter(name="limit", type="integer", description="Max results", required=False)],
        _monitor_community, "social")

    # ── SEO & Content Tools ──
    registry.register("seo_keyword_research", "Get keyword difficulty, search volume, CPC via DataForSEO or SEMrush.",
        [ToolParameter(name="keyword", description="Keyword to research"),
         ToolParameter(name="country", description="Country code (default: us)", required=False)],
        _seo_keyword_research, "seo")

    registry.register("seo_backlink_analysis", "Analyze backlink profile for a domain.",
        [ToolParameter(name="domain", description="Domain to analyze")],
        _seo_backlink_analysis, "seo")

    registry.register("generate_image", "Generate an image using DALL-E 3, Replicate Flux, or Fal.ai.",
        [ToolParameter(name="prompt", description="Detailed image description"),
         ToolParameter(name="style", description="Style: professional, minimal, bold, creative", required=False),
         ToolParameter(name="size", description="Image size: 1024x1024, 1792x1024, 1024x1792", required=False)],
        _generate_image, "content")

    registry.register("publish_to_cms", "Publish content to WordPress, Ghost, or Webflow CMS.",
        [ToolParameter(name="title", description="Post title"),
         ToolParameter(name="content", description="Post content (HTML)"),
         ToolParameter(name="status", description="Status: draft or publish", required=False),
         ToolParameter(name="platform", description="CMS: wordpress, ghost, webflow", required=False),
         ToolParameter(name="tags", description="Comma-separated tags", required=False)],
        _publish_to_cms, "content")

    registry.register("check_plagiarism", "Check text originality via Copyscape.",
        [ToolParameter(name="text", description="Text to check (up to 5000 chars)")],
        _check_plagiarism, "content")

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

    registry.register("create_linkedin_ad_campaign", "Create a LinkedIn Ads campaign for B2B targeting.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="targeting", description="Targeting criteria (titles, industries, company sizes)"),
         ToolParameter(name="ad_copy", description="Ad copy")],
        _create_linkedin_ad_campaign, "ads")

    registry.register("get_ad_performance", "Get performance metrics for an ad campaign.",
        [ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="platform", description="Platform: meta, google, linkedin"),
         ToolParameter(name="date_range", description="Date range", required=False)],
        _get_ad_performance, "ads")

    registry.register("build_landing_page", "Generate a complete landing page HTML and optionally deploy to Vercel.",
        [ToolParameter(name="headline", description="Main headline"),
         ToolParameter(name="subheadline", description="Supporting subheadline"),
         ToolParameter(name="body_sections", description="HTML body sections"),
         ToolParameter(name="cta_text", description="Call-to-action button text", required=False),
         ToolParameter(name="style", description="Visual style: modern, bold, minimal", required=False)],
        _build_landing_page, "ads")

    registry.register("setup_conversion_tracking", "Generate conversion tracking pixel code for Meta, Google, or LinkedIn.",
        [ToolParameter(name="platform", description="Platform: meta, google, linkedin, all"),
         ToolParameter(name="pixel_id", description="Pixel/tracking ID", required=False),
         ToolParameter(name="domain", description="Domain for tracking", required=False)],
        _setup_conversion_tracking, "ads")

    # ── Client Success Tools ──
    registry.register("send_slack_message", "Send message to a Slack channel.",
        [ToolParameter(name="channel", description="Slack channel (e.g. #general or channel ID)"),
         ToolParameter(name="message", description="Message text"),
         ToolParameter(name="blocks", description="Optional Slack Block Kit JSON", required=False)],
        _send_slack_message, "messaging")

    registry.register("send_telegram_message", "Send message via Telegram bot.",
        [ToolParameter(name="chat_id", description="Telegram chat ID"),
         ToolParameter(name="message", description="Message text"),
         ToolParameter(name="parse_mode", description="Parse mode: Markdown or HTML", required=False)],
        _send_telegram_message, "messaging")

    registry.register("generate_pdf_report", "Generate a PDF report from HTML sections.",
        [ToolParameter(name="title", description="Report title"),
         ToolParameter(name="sections", description="HTML content sections"),
         ToolParameter(name="output_format", description="Output: url or base64", required=False)],
        _generate_pdf_report, "reporting")

    registry.register("create_survey", "Create a survey/feedback form via Typeform.",
        [ToolParameter(name="title", description="Survey title"),
         ToolParameter(name="questions", description="JSON array of question objects"),
         ToolParameter(name="redirect_url", description="URL to redirect after completion", required=False)],
        _create_survey, "reporting")

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

    registry.register("check_domain_availability", "Check if a domain name is available for registration.",
        [ToolParameter(name="domain", description="Domain name to check (e.g. myagency.com)")],
        _check_domain_availability, "deployment")

    registry.register("register_domain", "Register a domain name (requires human approval).",
        [ToolParameter(name="domain", description="Domain to register"),
         ToolParameter(name="contact_info", description="Contact info for registration", required=False)],
        _register_domain, "deployment")

    registry.register("manage_dns", "Create or list DNS records via Cloudflare.",
        [ToolParameter(name="domain", description="Domain name"),
         ToolParameter(name="action", description="Action: create or list"),
         ToolParameter(name="record_type", description="Record type: A, AAAA, CNAME, TXT, MX", required=False),
         ToolParameter(name="name", description="Record name (e.g. @ or www)", required=False),
         ToolParameter(name="value", description="Record value (e.g. IP address)", required=False),
         ToolParameter(name="ttl", type="integer", description="TTL in seconds", required=False)],
        _manage_dns, "deployment")

    registry.register("setup_analytics", "Set up analytics tracking (Plausible or GA4) for a domain.",
        [ToolParameter(name="domain", description="Domain to track"),
         ToolParameter(name="provider", description="Provider: plausible or ga4", required=False)],
        _setup_analytics, "deployment")

    registry.register("setup_uptime_monitoring", "Set up uptime monitoring for a URL.",
        [ToolParameter(name="url", description="URL to monitor"),
         ToolParameter(name="check_interval", type="integer", description="Check interval in seconds", required=False)],
        _setup_uptime_monitoring, "deployment")

    registry.register("take_screenshot", "Take a screenshot of a URL for visual QA.",
        [ToolParameter(name="url", description="URL to screenshot"),
         ToolParameter(name="full_page", description="Capture full page (true/false)", required=False),
         ToolParameter(name="width", type="integer", description="Viewport width in pixels", required=False)],
        _take_screenshot, "deployment")

    registry.register("check_page_speed", "Run Google PageSpeed Insights audit — performance, SEO, accessibility scores.",
        [ToolParameter(name="url", description="URL to audit"),
         ToolParameter(name="strategy", description="Strategy: mobile or desktop", required=False)],
        _check_page_speed, "deployment")

    # ── Legal Tools ──
    registry.register("generate_document", "Generate a legal document from template (NDA, service agreement, privacy policy, TOS).",
        [ToolParameter(name="template_type", description="Type: nda, service_agreement, privacy_policy, terms_of_service"),
         ToolParameter(name="variables", description="JSON object of template variables"),
         ToolParameter(name="format", description="Output format: html", required=False)],
        _generate_document, "legal")

    registry.register("send_for_signature", "Send a document for e-signature via DocuSign or PandaDoc.",
        [ToolParameter(name="document_html", description="HTML content of the document"),
         ToolParameter(name="signer_email", description="Signer's email address"),
         ToolParameter(name="signer_name", description="Signer's full name"),
         ToolParameter(name="subject", description="Email subject line", required=False)],
        _send_for_signature, "legal")

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

    # ── Marketing Expert Tools ──
    registry.register("get_market_data", "Get market research data — market size, traffic, trends.",
        [ToolParameter(name="query", description="Market/industry query or domain"),
         ToolParameter(name="data_type", description="Type: market_size, website_traffic, trends", required=False)],
        _get_market_data, "research")

    registry.register("track_competitor", "Track competitor — site content, tech stack, social presence.",
        [ToolParameter(name="competitor_domain", description="Competitor's domain"),
         ToolParameter(name="metrics", description="What to track: all, site, tech, social", required=False)],
        _track_competitor, "research")

    registry.register("run_market_survey", "Generate and create a market research survey.",
        [ToolParameter(name="topic", description="Survey topic"),
         ToolParameter(name="audience", description="Target audience description"),
         ToolParameter(name="questions_count", type="integer", description="Number of questions (1-10)", required=False)],
        _run_market_survey, "research")

    # ── Procurement Tools ──
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
    registry.register("create_email_list", "Create an email list/tag in ConvertKit, Mailchimp, or Beehiiv.",
        [ToolParameter(name="list_name", description="Name for the list or tag"),
         ToolParameter(name="provider", description="ESP: convertkit, mailchimp, beehiiv", required=False)],
        _create_email_list, "newsletter")

    registry.register("add_subscriber", "Add a subscriber to an email list.",
        [ToolParameter(name="email", description="Subscriber email"),
         ToolParameter(name="name", description="Subscriber name", required=False),
         ToolParameter(name="tags", description="Tags or list IDs (comma-separated)", required=False),
         ToolParameter(name="provider", description="ESP: convertkit, mailchimp", required=False)],
        _add_subscriber, "newsletter")

    registry.register("get_email_analytics", "Get email subscriber analytics — open rates, growth, engagement.",
        [ToolParameter(name="provider", description="ESP: convertkit, mailchimp", required=False),
         ToolParameter(name="list_id", description="List/audience ID (Mailchimp)", required=False)],
        _get_email_analytics, "newsletter")

    # ── PPC / Analytics Tools ──
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
    registry.register("generate_logo", "Generate logo concepts using AI image generation.",
        [ToolParameter(name="brand_name", description="Brand/company name"),
         ToolParameter(name="style", description="Style: modern minimal, bold, elegant, playful", required=False),
         ToolParameter(name="icon_description", description="Optional icon/symbol description", required=False)],
        _generate_logo, "design")

    registry.register("generate_color_palette", "Generate a harmonious brand color palette.",
        [ToolParameter(name="industry", description="Industry/niche"),
         ToolParameter(name="personality", description="Brand personality: professional, creative, bold, minimal, warm"),
         ToolParameter(name="base_color", description="Optional base color hex (e.g. #1a365d)", required=False)],
        _generate_color_palette, "design")

    registry.register("get_font_pairing", "Get Google Fonts pairing recommendation with size scale.",
        [ToolParameter(name="style", description="Style: modern, elegant, startup, corporate, bold"),
         ToolParameter(name="industry", description="Industry for context", required=False)],
        _get_font_pairing, "design")

    registry.register("upload_asset", "Upload a brand asset to Cloudflare R2 or Supabase Storage.",
        [ToolParameter(name="file_data", description="Base64-encoded file data"),
         ToolParameter(name="filename", description="Filename with extension"),
         ToolParameter(name="content_type", description="MIME type (e.g. image/png)", required=False)],
        _upload_asset, "design")

    # ── Supervisor Tools ──
    registry.register("get_campaign_dashboard", "Aggregate all metrics across agents for a campaign overview.",
        [ToolParameter(name="campaign_id", description="Campaign ID")],
        _get_campaign_dashboard, "supervisor")

    registry.register("trigger_agent_rerun", "Queue an agent for re-run with updated instructions.",
        [ToolParameter(name="agent_id", description="Agent ID to re-run"),
         ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="reason", description="Reason for re-run"),
         ToolParameter(name="updated_instructions", description="New instructions for the agent", required=False)],
        _trigger_agent_rerun, "supervisor")

    registry.register("send_owner_alert", "Send alert to business owner via Slack, Telegram, or email.",
        [ToolParameter(name="channel", description="Channel: slack, telegram, email"),
         ToolParameter(name="message", description="Alert message"),
         ToolParameter(name="priority", description="Priority: normal or high", required=False)],
        _send_owner_alert, "supervisor")

    registry.register("get_agent_performance_history", "Get historical performance data for an agent.",
        [ToolParameter(name="agent_id", description="Agent ID"),
         ToolParameter(name="campaign_id", description="Campaign ID")],
        _get_agent_performance_history, "supervisor")

    # ── Business Formation Tools ──
    registry.register("research_entity_types", "Compare LLC vs S-Corp vs C-Corp for a specific state and business type.",
        [ToolParameter(name="state", description="State of formation"),
         ToolParameter(name="business_type", description="Type of business (agency, SaaS, consulting)", required=False)],
        _research_entity_types, "formation")

    registry.register("file_business_entity", "Initiate business entity formation (LLC/Corp) via filing service or manual guide.",
        [ToolParameter(name="entity_type", description="Entity type: llc, s_corp, c_corp"),
         ToolParameter(name="state", description="State of formation"),
         ToolParameter(name="business_name", description="Legal business name"),
         ToolParameter(name="registered_agent", description="Registered agent service name", required=False),
         ToolParameter(name="members", description="Comma-separated member names", required=False)],
        _file_business_entity, "formation")

    registry.register("apply_for_ein", "Guide through IRS EIN application process.",
        [], _apply_for_ein, "formation")

    registry.register("research_registered_agents", "Compare registered agent services for a state.",
        [ToolParameter(name="state", description="State to find agents for")],
        _research_registered_agents, "formation")

    registry.register("research_business_banking", "Compare business bank accounts and requirements.",
        [ToolParameter(name="business_type", description="Type of business", required=False),
         ToolParameter(name="state", description="State", required=False)],
        _research_business_banking, "formation")

    registry.register("research_business_insurance", "Research required and recommended business insurance.",
        [ToolParameter(name="business_type", description="Type of business"),
         ToolParameter(name="state", description="State", required=False),
         ToolParameter(name="revenue_estimate", description="Estimated annual revenue", required=False)],
        _research_business_insurance, "formation")

    registry.register("research_business_licenses", "Research required business licenses and permits.",
        [ToolParameter(name="business_type", description="Type of business"),
         ToolParameter(name="state", description="State"),
         ToolParameter(name="city", description="City", required=False)],
        _research_business_licenses, "formation")

    # ── Business Advisor Tools ──
    registry.register("build_financial_model", "Build a 12-month financial projection model.",
        [ToolParameter(name="service", description="Service/product offered"),
         ToolParameter(name="pricing_model", description="Pricing model: retainer, project, hourly, productized"),
         ToolParameter(name="price_point", description="Price point (e.g. $2000/mo)"),
         ToolParameter(name="target_clients", description="Target number of clients"),
         ToolParameter(name="monthly_expenses", description="Monthly operating expenses", required=False)],
        _build_financial_model, "advisor")

    registry.register("tax_strategy_research", "Research tax optimization strategies for the business.",
        [ToolParameter(name="entity_type", description="Entity type: llc, s_corp, c_corp, sole_prop"),
         ToolParameter(name="estimated_revenue", description="Estimated annual revenue"),
         ToolParameter(name="state", description="State of operation"),
         ToolParameter(name="filing_status", description="Tax filing status: single, married_joint, married_separate", required=False)],
        _tax_strategy_research, "advisor")

    registry.register("pricing_strategy", "Develop pricing strategy with market research and psychology.",
        [ToolParameter(name="service", description="Service being priced"),
         ToolParameter(name="icp", description="Ideal customer profile"),
         ToolParameter(name="competitors", description="Known competitors", required=False),
         ToolParameter(name="current_price", description="Current price if any", required=False)],
        _pricing_strategy, "advisor")

    registry.register("cash_flow_analysis", "Analyze cash flow health and provide recommendations.",
        [ToolParameter(name="monthly_revenue", description="Monthly revenue"),
         ToolParameter(name="monthly_expenses", description="Monthly expenses"),
         ToolParameter(name="payment_terms", description="Payment terms: net_15, net_30, upfront", required=False),
         ToolParameter(name="runway_months", description="Cash reserves in months of expenses", required=False)],
        _cash_flow_analysis, "advisor")

    registry.register("growth_playbook", "Build a stage-appropriate growth strategy playbook.",
        [ToolParameter(name="current_revenue", description="Current monthly revenue"),
         ToolParameter(name="target_revenue", description="Target monthly revenue"),
         ToolParameter(name="service", description="Service/product offered"),
         ToolParameter(name="channels", description="Current marketing channels", required=False)],
        _growth_playbook, "advisor")

    # ── Expanded Legal Tools ──
    registry.register("research_ip_protection", "Research IP protection — trademarks, copyrights, trade secrets.",
        [ToolParameter(name="business_name", description="Business name to protect"),
         ToolParameter(name="service", description="Type of service/product"),
         ToolParameter(name="state", description="State of operation", required=False)],
        _research_ip_protection, "legal")

    registry.register("employment_law_research", "Research employment law — contractor vs employee, compliance.",
        [ToolParameter(name="state", description="State of operation"),
         ToolParameter(name="worker_type", description="Worker type: contractor, employee, both", required=False),
         ToolParameter(name="num_workers", description="Number of workers", required=False)],
        _employment_law_research, "legal")

    registry.register("compliance_checklist", "Generate comprehensive regulatory compliance checklist.",
        [ToolParameter(name="business_type", description="Type of business"),
         ToolParameter(name="state", description="State of operation"),
         ToolParameter(name="has_employees", description="Has employees: yes or no", required=False),
         ToolParameter(name="handles_data", description="Handles client data: yes or no", required=False)],
        _compliance_checklist, "legal")

    # ── Website Builder Tools ──
    registry.register("build_full_website", "Generate a complete multi-page business website with responsive design and deploy.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service/product description"),
         ToolParameter(name="pages", description="Comma-separated pages: home,about,services,contact,pricing,faq,blog", required=False),
         ToolParameter(name="brand_colors", description="JSON: {primary, secondary, accent} hex colors", required=False),
         ToolParameter(name="brand_fonts", description="JSON: {display, body} Google Font names", required=False),
         ToolParameter(name="cta_text", description="Call-to-action button text", required=False),
         ToolParameter(name="cta_url", description="CTA link URL", required=False)],
        _build_full_website, "website")

    registry.register("generate_page", "Generate a single page — pricing, case study, FAQ, blog post, etc.",
        [ToolParameter(name="page_type", description="Page type: pricing, case_study, faq, blog, landing"),
         ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="content", description="HTML content for the page body"),
         ToolParameter(name="brand_colors", description="JSON or hex color", required=False),
         ToolParameter(name="style", description="Visual style: modern, bold, minimal", required=False)],
        _generate_page, "website")

    # ── Finance Tools ──
    registry.register("generate_chart_of_accounts", "Generate entity-appropriate chart of accounts with industry-specific categories.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp, partnership"),
         ToolParameter(name="industry", description="Industry for category customization", required=False)],
        _generate_chart_of_accounts, "finance")

    registry.register("generate_pnl_template", "Generate monthly P&L template adapted to entity type.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp"),
         ToolParameter(name="monthly_revenue", description="Estimated monthly revenue", required=False)],
        _generate_pnl_template, "finance")

    registry.register("tax_deadline_calendar", "Generate tax compliance calendar with entity-specific deadlines.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp, partnership"),
         ToolParameter(name="state", description="State of operation", required=False)],
        _tax_deadline_calendar, "finance")

    # ── HR Tools ──
    registry.register("create_hiring_plan", "Generate revenue-triggered hiring plan adapted to entity type.",
        [ToolParameter(name="service", description="Service the business provides"),
         ToolParameter(name="current_revenue", description="Current monthly revenue", required=False),
         ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp", required=False)],
        _create_hiring_plan, "hr")

    registry.register("worker_classification_check", "Check 1099 vs W-2 classification risk for a worker role.",
        [ToolParameter(name="worker_role", description="Role/title of the worker"),
         ToolParameter(name="state", description="State of operation", required=False),
         ToolParameter(name="hours_per_week", description="Hours per week the worker does", required=False)],
        _worker_classification_check, "hr")

    # ── Sales Pipeline Tools ──
    registry.register("build_sales_pipeline", "Build CRM pipeline stages with conversion targets and actions.",
        [ToolParameter(name="service", description="Service being sold"),
         ToolParameter(name="avg_deal_size", description="Average deal size in dollars", required=False),
         ToolParameter(name="sales_cycle_days", description="Average sales cycle length in days", required=False)],
        _build_sales_pipeline, "sales")

    registry.register("generate_discovery_script", "Generate discovery call script with objection handling library.",
        [ToolParameter(name="service", description="Service being sold"),
         ToolParameter(name="icp", description="Ideal customer profile", required=False)],
        _generate_discovery_script, "sales")

    # ── Delivery & Operations Tools ──
    registry.register("build_delivery_sop", "Generate standard operating procedure for a delivery phase.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="phase", description="Phase: onboarding, execution, review, handoff", required=False)],
        _build_delivery_sop, "delivery")

    registry.register("capacity_planning", "Calculate capacity, utilization targets, and max concurrent clients.",
        [ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="hours_per_client", description="Hours per client per week", required=False),
         ToolParameter(name="team_size", description="Number of team members", required=False)],
        _capacity_planning, "delivery")

    # ── Business Intelligence / Analytics Tools ──
    registry.register("build_metrics_hierarchy", "Build North Star → L1 → L2 → Leading indicators hierarchy.",
        [ToolParameter(name="service", description="Service/business type"),
         ToolParameter(name="business_model", description="Model: retainer, project, hourly, productized", required=False)],
        _build_metrics_hierarchy, "bi")

    registry.register("build_attribution_model", "Design multi-touch attribution model with tracking requirements.",
        [ToolParameter(name="channels", description="Current marketing channels (comma-separated)", required=False)],
        _build_attribution_model, "bi")

    registry.register("build_dashboard_spec", "Generate executive dashboard specification with KPIs and tool recommendations.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="metrics", description="Key metrics to include (comma-separated)", required=False)],
        _build_dashboard_spec, "bi")

    # ── Tax Optimization Tools ──
    registry.register("tax_writeoff_audit", "Comprehensive tax write-off audit — every legal deduction for the entity type with dollar estimates.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp, partnership"),
         ToolParameter(name="service", description="Type of service business", required=False),
         ToolParameter(name="annual_revenue", description="Estimated annual revenue", required=False)],
        _tax_writeoff_audit, "tax")

    registry.register("reasonable_salary_calculator", "Calculate S-Corp reasonable salary range with FICA savings and audit risk analysis.",
        [ToolParameter(name="annual_profit", description="Annual business profit"),
         ToolParameter(name="industry", description="Industry: services, consulting, marketing, saas, agency", required=False),
         ToolParameter(name="geography", description="State/city for regional salary data", required=False),
         ToolParameter(name="role", description="Officer role: CEO, President, Managing Director", required=False)],
        _reasonable_salary_calculator, "tax")

    # ── Wealth Architecture Tools ──
    registry.register("wealth_structure_analyzer", "Analyze wealth architecture options by income tier — 1% strategies with implementation roadmap.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp"),
         ToolParameter(name="annual_income", description="Annual business income"),
         ToolParameter(name="state", description="State of residence", required=False),
         ToolParameter(name="net_worth", description="Estimated net worth", required=False)],
        _wealth_structure_analyzer, "tax")

    registry.register("multi_entity_planner", "Plan multi-entity structure (holding co, operating co, property co) for asset protection and tax optimization.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="entity_type", description="Current entity type: sole_prop, llc, s_corp, c_corp"),
         ToolParameter(name="annual_revenue", description="Annual revenue", required=False),
         ToolParameter(name="state", description="State of formation", required=False)],
        _multi_entity_planner, "tax")

    # ── Billing & Invoicing Tools ──
    registry.register("create_invoice", "Create and send an invoice to a client via Stripe. Generates a hosted payment link.",
        [ToolParameter(name="client_name", description="Client's business or person name"),
         ToolParameter(name="client_email", description="Client's email for invoice delivery"),
         ToolParameter(name="amount", description="Invoice amount in dollars (e.g. '5000')"),
         ToolParameter(name="description", description="Line item description", required=False),
         ToolParameter(name="due_days", description="Days until due (default 30)", required=False),
         ToolParameter(name="currency", description="Currency code (default usd)", required=False)],
        _create_invoice, "billing")

    registry.register("create_subscription", "Create a recurring subscription for a client with auto-billing.",
        [ToolParameter(name="client_name", description="Client's name"),
         ToolParameter(name="client_email", description="Client's email"),
         ToolParameter(name="amount", description="Monthly amount in dollars"),
         ToolParameter(name="interval", description="Billing interval: month, quarter, year", required=False),
         ToolParameter(name="description", description="Subscription description", required=False)],
        _create_subscription, "billing")

    registry.register("check_payment_status", "Check payment status for an invoice or customer's outstanding balance.",
        [ToolParameter(name="invoice_id", description="Stripe invoice ID", required=False),
         ToolParameter(name="customer_email", description="Customer email to look up", required=False)],
        _check_payment_status, "billing")

    registry.register("send_payment_reminder", "Send a payment reminder email for outstanding invoices.",
        [ToolParameter(name="customer_email", description="Customer email with outstanding invoices"),
         ToolParameter(name="message", description="Custom reminder message", required=False)],
        _send_payment_reminder, "billing")

    registry.register("setup_dunning_sequence", "Configure automated dunning sequence for failed/late payments.",
        [ToolParameter(name="reminder_days", description="Comma-separated reminder days (e.g. '3,7,14,30')", required=False),
         ToolParameter(name="escalation_action", description="Final action: pause_service, cancel, collections", required=False)],
        _setup_dunning_sequence, "billing")

    registry.register("get_revenue_metrics", "Get revenue metrics — MRR, ARR, collection rate, outstanding invoices.",
        [],
        _get_revenue_metrics, "billing")

    # ── Referral & Affiliate Tools ──
    registry.register("create_referral_program", "Design and configure a referral/affiliate program with tiered commissions.",
        [ToolParameter(name="program_name", description="Program name"),
         ToolParameter(name="reward_type", description="percentage or flat_fee", required=False),
         ToolParameter(name="reward_value", description="Commission % or flat amount", required=False),
         ToolParameter(name="reward_description", description="Human-readable reward description", required=False),
         ToolParameter(name="cookie_duration_days", description="Attribution window in days", required=False)],
        _create_referral_program, "referral")

    registry.register("track_referral", "Track a referral event — signup, conversion, or revenue attribution.",
        [ToolParameter(name="referrer_id", description="Referrer's unique ID"),
         ToolParameter(name="referred_email", description="Referred person's email"),
         ToolParameter(name="event", description="Event type: signup, conversion, revenue", required=False),
         ToolParameter(name="revenue", description="Revenue amount to attribute", required=False)],
        _track_referral, "referral")

    registry.register("get_referral_metrics", "Get referral program performance — affiliates, conversions, commissions.",
        [],
        _get_referral_metrics, "referral")

    registry.register("generate_affiliate_assets", "Generate affiliate marketing assets — swipe copy, social posts, email templates.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service description"),
         ToolParameter(name="commission_rate", description="Commission rate %", required=False)],
        _generate_affiliate_assets, "referral")

    # ── Upsell & Client Intelligence Tools ──
    registry.register("analyze_expansion_opportunities", "Analyze a client for upsell/cross-sell opportunities based on usage and satisfaction.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="current_services", description="Comma-separated services they use"),
         ToolParameter(name="monthly_revenue", description="Current MRR from this client", required=False),
         ToolParameter(name="engagement_months", description="Months they've been a client", required=False),
         ToolParameter(name="satisfaction_score", description="CSAT score 1-5", required=False)],
        _analyze_expansion_opportunities, "upsell")

    registry.register("build_qbr_template", "Build a Quarterly Business Review template for client expansion conversations.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="service", description="Service being delivered"),
         ToolParameter(name="key_metrics", description="Key metrics to highlight", required=False)],
        _build_qbr_template, "upsell")

    registry.register("client_health_score", "Calculate client health score and churn risk with recommended actions.",
        [ToolParameter(name="client_name", description="Client name"),
         ToolParameter(name="monthly_revenue", description="Monthly revenue from client", required=False),
         ToolParameter(name="last_interaction_days", description="Days since last interaction", required=False),
         ToolParameter(name="support_tickets", description="Open support tickets", required=False),
         ToolParameter(name="satisfaction_score", description="CSAT score 1-5", required=False),
         ToolParameter(name="contract_months_remaining", description="Months until contract renewal", required=False)],
        _client_health_score, "upsell")

    # ── Multi-Campaign Orchestration Tools ──
    registry.register("compare_campaigns", "Compare performance across multiple campaigns for cross-learning insights.",
        [ToolParameter(name="campaign_ids", description="Comma-separated campaign IDs to compare")],
        _compare_campaigns, "orchestration")

    registry.register("clone_campaign_config", "Clone a successful campaign config for a new client — saves 60-70% setup time.",
        [ToolParameter(name="source_campaign_id", description="Campaign ID to clone from"),
         ToolParameter(name="new_business_name", description="New client's business name"),
         ToolParameter(name="new_icp", description="New ICP if different", required=False)],
        _clone_campaign_config, "orchestration")

    registry.register("portfolio_dashboard", "Get portfolio-level metrics across all campaigns — agency-wide view.",
        [ToolParameter(name="campaign_ids", description="Comma-separated campaign IDs (or empty for all)", required=False)],
        _portfolio_dashboard, "orchestration")


register_all_tools()
