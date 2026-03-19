"""
Business entity formation, EIN, registered agents, banking, insurance, and licenses.
"""

from __future__ import annotations

import json


from config import settings

from tools.research import _web_search
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



def register_formation_tools(registry):
    """Register all formation tools with the given registry."""
    from models import ToolParameter

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

