"""
Harvey AI legal research, contract analysis, regulatory analysis, and case law search.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _harvey_legal_research(query: str, jurisdiction: str = "us_federal", area: str = "general") -> str:
    """Research legal questions using Harvey AI."""
    if not settings.harvey_api_key:
        return json.dumps({
            "query": query, "jurisdiction": jurisdiction, "area": area, "draft": True,
            "analysis": {
                "summary": f"Legal research query: {query}",
                "jurisdiction": jurisdiction,
                "practice_area": area,
                "key_considerations": [
                    "Consult qualified attorney for binding legal advice",
                    "Jurisdiction-specific rules may apply",
                    "Regulatory landscape changes frequently",
                ],
                "recommended_actions": [
                    "Configure HARVEY_API_KEY for AI-powered legal research",
                    "Cross-reference with primary legal sources",
                    "Consider engaging local counsel for jurisdiction-specific matters",
                ],
            },
            "note": "Configure HARVEY_API_KEY for AI-powered legal research with case law citations.",
        })
    try:
        resp = await _http.post(
            "https://api.harvey.ai/v1/research",
            headers={"Authorization": f"Bearer {settings.harvey_api_key}", "Content-Type": "application/json"},
            json={"query": query, "jurisdiction": jurisdiction, "practice_area": area},
            timeout=60,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Harvey API returned {resp.status_code}", "detail": resp.text[:500]})
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})



async def _harvey_contract_analysis(contract_text: str, analysis_type: str = "review", focus: str = "") -> str:
    """Analyze contracts using Harvey AI — review, risk assessment, clause extraction."""
    if not settings.harvey_api_key:
        focus_label = f" focusing on {focus}" if focus else ""
        return json.dumps({
            "analysis_type": analysis_type, "focus": focus, "draft": True,
            "review": {
                "contract_length": len(contract_text),
                "analysis_requested": f"{analysis_type}{focus_label}",
                "standard_checks": [
                    "Indemnification clauses — scope and caps",
                    "Limitation of liability — consequential damages carve-outs",
                    "Termination provisions — for cause vs convenience, notice periods",
                    "IP ownership and assignment — work product, pre-existing IP",
                    "Confidentiality — duration, exceptions, return of materials",
                    "Non-compete/non-solicit — geographic and temporal scope",
                    "Governing law and dispute resolution — arbitration vs litigation",
                    "Data protection and privacy — GDPR, CCPA compliance",
                    "Force majeure — scope and notification requirements",
                    "Payment terms — net terms, late fees, currency",
                ],
                "risk_flags": "Configure HARVEY_API_KEY for automated risk flagging",
            },
            "note": "Configure HARVEY_API_KEY for deep AI-powered contract analysis.",
        })
    try:
        resp = await _http.post(
            "https://api.harvey.ai/v1/contracts/analyze",
            headers={"Authorization": f"Bearer {settings.harvey_api_key}", "Content-Type": "application/json"},
            json={"text": contract_text, "type": analysis_type, "focus": focus},
            timeout=60,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Harvey API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _harvey_regulatory_analysis(regulation: str, industry: str = "", jurisdiction: str = "us_federal") -> str:
    """Analyze regulatory requirements and compliance obligations."""
    if not settings.harvey_api_key:
        return json.dumps({
            "regulation": regulation, "industry": industry, "jurisdiction": jurisdiction, "draft": True,
            "analysis": {
                "common_frameworks": {
                    "data_privacy": ["GDPR (EU)", "CCPA/CPRA (California)", "PIPEDA (Canada)", "LGPD (Brazil)", "state privacy laws"],
                    "financial": ["SOX", "PCI-DSS", "BSA/AML", "SEC regulations", "state money transmitter laws"],
                    "healthcare": ["HIPAA", "HITECH", "FDA regulations", "state telehealth laws"],
                    "employment": ["FLSA", "FMLA", "ADA", "Title VII", "state labor codes", "OSHA"],
                    "ai_specific": ["EU AI Act", "NYC Local Law 144", "state AI disclosure laws", "FTC AI guidance"],
                    "advertising": ["FTC Act Section 5", "CAN-SPAM", "TCPA", "Lanham Act", "NAD guidelines"],
                },
                "compliance_steps": [
                    "Identify applicable regulations for business type and jurisdictions",
                    "Map data flows and processing activities",
                    "Conduct gap analysis against requirements",
                    "Implement required controls and documentation",
                    "Establish ongoing monitoring and reporting",
                ],
            },
            "note": "Configure HARVEY_API_KEY for regulation-specific AI analysis.",
        })
    try:
        resp = await _http.post(
            "https://api.harvey.ai/v1/regulatory",
            headers={"Authorization": f"Bearer {settings.harvey_api_key}", "Content-Type": "application/json"},
            json={"regulation": regulation, "industry": industry, "jurisdiction": jurisdiction},
            timeout=60,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Harvey API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _harvey_case_law_search(query: str, jurisdiction: str = "us_federal", court_level: str = "all") -> str:
    """Search case law for precedents and relevant decisions."""
    if not settings.harvey_api_key:
        return json.dumps({
            "query": query, "jurisdiction": jurisdiction, "court_level": court_level, "draft": True,
            "guidance": {
                "search_query": query,
                "free_alternatives": [
                    "Google Scholar (scholar.google.com) — case law search",
                    "CourtListener (courtlistener.com) — free legal research",
                    "Casetext (via CoCounsel) — AI-assisted research",
                    "PACER — federal court filings",
                ],
                "search_strategies": [
                    "Use Boolean operators for precision",
                    "Filter by jurisdiction and date range",
                    "Check citing references for current validity",
                    "Verify holdings haven't been overruled (Shepardize)",
                ],
            },
            "note": "Configure HARVEY_API_KEY for comprehensive AI-powered case law search.",
        })
    try:
        resp = await _http.post(
            "https://api.harvey.ai/v1/case-law/search",
            headers={"Authorization": f"Bearer {settings.harvey_api_key}", "Content-Type": "application/json"},
            json={"query": query, "jurisdiction": jurisdiction, "court_level": court_level},
            timeout=60,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Harvey API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_harvey_tools(registry):
    """Register all harvey tools with the given registry."""
    from models import ToolParameter

    registry.register("harvey_legal_research", "Research legal questions with AI-powered case law analysis and citations.",
        [ToolParameter(name="query", description="Legal research question"),
         ToolParameter(name="jurisdiction", description="Jurisdiction: us_federal, us_state, eu, uk, international", required=False),
         ToolParameter(name="area", description="Practice area: corporate, ip, employment, privacy, tax, regulatory, contracts", required=False)],
        _harvey_legal_research, "harvey")

    registry.register("harvey_contract_analysis", "Analyze contracts — risk assessment, clause extraction, redline suggestions.",
        [ToolParameter(name="contract_text", description="Contract text to analyze"),
         ToolParameter(name="analysis_type", description="Type: review, risk_assessment, clause_extraction, redline, summary", required=False),
         ToolParameter(name="focus", description="Focus areas: indemnification, ip, termination, liability, data_privacy", required=False)],
        _harvey_contract_analysis, "harvey")

    registry.register("harvey_regulatory_analysis", "Analyze regulatory requirements and compliance obligations for specific industries.",
        [ToolParameter(name="regulation", description="Regulation or compliance area: gdpr, ccpa, hipaa, sox, pci_dss, ai_act, etc."),
         ToolParameter(name="industry", description="Industry: saas, fintech, healthcare, ecommerce, etc.", required=False),
         ToolParameter(name="jurisdiction", description="Jurisdiction: us_federal, eu, uk, california, etc.", required=False)],
        _harvey_regulatory_analysis, "harvey")

    registry.register("harvey_case_law_search", "Search case law for precedents, relevant decisions, and legal analysis.",
        [ToolParameter(name="query", description="Case law search query"),
         ToolParameter(name="jurisdiction", description="Jurisdiction: us_federal, us_state, eu, uk", required=False),
         ToolParameter(name="court_level", description="Court: supreme, appellate, district, all", required=False)],
        _harvey_case_law_search, "harvey")

    # ── Expanded Full-Stack Dev Tools (Mobile, Desktop, Extensions, AI, CLI, Microservices) ──

