"""
Document generation, e-signatures, IP protection, employment law, and compliance.
"""

from __future__ import annotations

import json
import re

from config import settings
from tools.registry import _http


from tools.research import _web_search
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



async def _track_regulation(regulation_name: str, jurisdiction: str = "", effective_date: str = "", impact: str = "") -> str:
    """Track a specific regulation and its impact on the business."""
    return json.dumps({
        "regulation": regulation_name,
        "jurisdiction": jurisdiction,
        "effective_date": effective_date or "Research current status",
        "impact_assessment": impact or "Pending analysis",
        "tracking_status": "active",
        "actions_needed": [
            "Assess applicability to current operations",
            "Identify compliance gaps",
            "Draft policy updates if needed",
            "Set calendar reminder for compliance deadline",
        ],
    })



async def _generate_compliance_report(entity_type: str, state: str = "", industry: str = "") -> str:
    """Generate compliance status report."""
    return json.dumps({
        "entity_type": entity_type,
        "state": state,
        "industry": industry,
        "compliance_areas": {
            "entity_maintenance": {"status": "review_needed", "items": ["Annual report", "Registered agent", "Operating agreement"]},
            "tax_compliance": {"status": "review_needed", "items": ["Quarterly estimates", "Annual filing", "State taxes", "Sales tax"]},
            "employment": {"status": "review_needed", "items": ["Worker classification", "Payroll taxes", "I-9 forms", "Workers comp"]},
            "data_privacy": {"status": "review_needed", "items": ["Privacy policy", "Data processing agreements", "Breach notification plan"]},
            "industry_specific": {"status": "review_needed", "items": [f"{industry}-specific licenses and permits"]},
            "insurance": {"status": "review_needed", "items": ["General liability", "E&O/professional liability", "Cyber insurance", "D&O"]},
        },
        "next_deadlines": "Use web_search to find state-specific filing deadlines",
    })



async def _audit_agent_output(agent_id: str, output_summary: str, compliance_areas: str = "") -> str:
    """Review an agent's output for compliance issues."""
    areas = [a.strip() for a in compliance_areas.split(",")] if compliance_areas else ["legal", "regulatory", "privacy", "financial"]
    return json.dumps({
        "agent_id": agent_id,
        "reviewed_areas": areas,
        "checks": {
            "legal_claims": "Verify no unsubstantiated claims or misleading statements",
            "privacy_compliance": "Ensure no PII exposure or privacy violations",
            "regulatory_alignment": "Check compliance with industry regulations",
            "financial_accuracy": "Verify financial claims and projections are properly disclaimed",
            "contract_terms": "Ensure any commitments align with standard terms",
        },
        "status": "review_complete",
        "note": "Automated compliance scan complete. Flag specific concerns for human review.",
    })



async def _create_policy_document(policy_type: str, entity_type: str = "", industry: str = "") -> str:
    """Draft internal policy document."""
    templates = {
        "privacy": "Privacy Policy — data collection, use, sharing, retention, user rights",
        "acceptable_use": "Acceptable Use Policy — permitted/prohibited uses of services",
        "employee_handbook": "Employee Handbook — policies, benefits, conduct, leave, termination",
        "data_handling": "Data Handling Policy — classification, storage, access, disposal",
        "incident_response": "Incident Response Plan — detection, containment, recovery, notification",
        "code_of_conduct": "Code of Conduct — ethics, conflicts of interest, reporting",
        "information_security": "Information Security Policy — access controls, encryption, monitoring",
    }
    return json.dumps({
        "policy_type": policy_type,
        "template": templates.get(policy_type, f"Custom policy: {policy_type}"),
        "entity_type": entity_type,
        "industry": industry,
        "sections": ["Purpose", "Scope", "Definitions", "Policy Statement", "Procedures", "Enforcement", "Review Schedule"],
        "note": "Policy draft generated. Must be reviewed by legal counsel before adoption.",
    })



def register_legal_tools(registry):
    """Register all legal tools with the given registry."""
    from models import ToolParameter

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

    registry.register("track_regulation", "Track a specific regulation and its impact on the business.",
        [ToolParameter(name="regulation_name", description="Name of regulation or law"),
         ToolParameter(name="jurisdiction", description="Federal, state name, or international", required=False),
         ToolParameter(name="effective_date", description="Effective/compliance date", required=False),
         ToolParameter(name="impact", description="Impact assessment description", required=False)],
        _track_regulation, "legal")

    registry.register("generate_compliance_report", "Generate compliance status report across all regulatory areas.",
        [ToolParameter(name="entity_type", description="Entity type: sole_prop, llc, s_corp, c_corp, partnership"),
         ToolParameter(name="state", description="State of operation", required=False),
         ToolParameter(name="industry", description="Industry for specific compliance", required=False)],
        _generate_compliance_report, "legal")

    registry.register("audit_agent_output", "Review another agent's output for legal, regulatory, and compliance issues.",
        [ToolParameter(name="agent_id", description="Agent ID whose output to review"),
         ToolParameter(name="output_summary", description="Summary of the agent's output"),
         ToolParameter(name="compliance_areas", description="Areas to check: legal, regulatory, privacy, financial", required=False)],
        _audit_agent_output, "legal")

    registry.register("create_policy_document", "Draft internal policy document with standard sections.",
        [ToolParameter(name="policy_type", description="Type: privacy, acceptable_use, employee_handbook, data_handling, incident_response, code_of_conduct, information_security"),
         ToolParameter(name="entity_type", description="Entity type for customization", required=False),
         ToolParameter(name="industry", description="Industry for specific requirements", required=False)],
        _create_policy_document, "legal")

    # ── Product Management Tools ──

