"""
Stripe billing, invoicing, subscriptions, revenue metrics, chart of accounts, and tax optimization.
"""

from __future__ import annotations

import json
import re

from config import settings
from tools.registry import _http


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



def register_finance_tools(registry):
    """Register all finance tools with the given registry."""
    from models import ToolParameter

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

