"""
Financial modeling, tax strategy, pricing, cash flow analysis, and growth playbooks.
"""

from __future__ import annotations

import json


from tools.research import _web_search
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



def register_advisor_tools(registry):
    """Register all advisor tools with the given registry."""
    from models import ToolParameter

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

