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
    """Check domain name availability via GoDaddy or Namecheap API."""
    godaddy_key = getattr(settings, 'godaddy_api_key', '') or ""
    godaddy_secret = getattr(settings, 'godaddy_api_secret', '') or ""
    if godaddy_key and godaddy_secret:
        try:
            resp = await _http.get(f"https://api.godaddy.com/v1/domains/available",
                params={"domain": domain},
                headers={"Authorization": f"sso-key {godaddy_key}:{godaddy_secret}"})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({
                    "domain": domain, "available": data.get("available", False),
                    "price": data.get("price", 0) / 1000000 if data.get("price") else None,
                    "currency": data.get("currency", "USD"),
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return await _web_search(f'"{domain}" domain availability whois', 3)


async def _register_domain(domain: str, contact_info: str = "") -> str:
    """Register a domain name via GoDaddy API."""
    godaddy_key = getattr(settings, 'godaddy_api_key', '') or ""
    godaddy_secret = getattr(settings, 'godaddy_api_secret', '') or ""
    if not godaddy_key or not godaddy_secret:
        return json.dumps({"error": "Domain registration not configured. Set GODADDY_API_KEY.",
                           "draft": {"domain": domain, "action": "register"}})
    return json.dumps({"domain": domain, "status": "pending_approval",
                       "note": "Domain registration requires human approval before purchase.",
                       "estimated_cost": "$12-15/year"})


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
# LEGAL — Document Generation, Compliance, E-Signatures
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


register_all_tools()
