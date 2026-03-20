"""
Apollo, Hunter, Clearbit lead enrichment, buyer intent, and LinkedIn prospecting tools.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


from tools.research import _web_search
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



def register_prospecting_tools(registry):
    """Register all prospecting tools with the given registry."""
    from models import ToolParameter

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

