"""
Omni OS Backend — Agent Performance Scoring
Scores agents on actual business outcomes, not output quality.
"""
from __future__ import annotations
import logging
from typing import Any

from models import Campaign

logger = logging.getLogger("supervisor.scoring")


GRADE_THRESHOLDS = [
    (95, "A+"), (90, "A"), (85, "A-"),
    (80, "B+"), (75, "B"), (70, "B-"),
    (60, "C+"), (55, "C"), (50, "C-"),
    (40, "D"), (0, "F"),
]


def _to_grade(score: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


class AgentScorer:
    """Scores agents on actual business outcomes."""

    def score_all(self, campaign: Campaign) -> dict[str, dict]:
        """Score every agent and return grades with reasoning."""
        results = {}
        metrics = getattr(campaign, '_metrics', {})

        scorers = {
            "prospector": self._score_prospector,
            "outreach": self._score_outreach,
            "content": self._score_content,
            "social": self._score_social,
            "ads": self._score_ads,
            "cs": self._score_cs,
            "sitelaunch": self._score_sitelaunch,
            "legal": self._score_legal,
            "marketing_expert": self._score_marketing_expert,
            "procurement": self._score_procurement,
            "newsletter": self._score_newsletter,
            "ppc": self._score_ppc,
            "finance": self._score_finance,
            "hr": self._score_hr,
            "sales": self._score_sales,
            "delivery": self._score_delivery,
            "analytics_agent": self._score_analytics,
            "tax_strategist": self._score_tax,
            "wealth_architect": self._score_wealth,
            "billing": self._score_billing,
            "referral": self._score_referral,
            "portfolio_ops": self._score_portfolio_ops,
            "competitive_intel": self._score_competitive_intel,
            "client_portal": self._score_client_portal,
            "voice_receptionist": self._score_voice_receptionist,
            "fullstack_dev": self._score_fullstack_dev,
            "economist": self._score_economist,
            "pr_comms": self._score_pr_comms,
            "data_engineer": self._score_data_engineer,
            "governance": self._score_governance,
            "product_manager": self._score_product_manager,
            "partnerships": self._score_partnerships,
            "client_fulfillment": self._score_client_fulfillment,
            "knowledge_engine": self._score_knowledge_engine,
            "agent_ops": self._score_agent_ops,
            "world_model": self._score_world_model,
            "formation": self._score_formation,
            "advisor": self._score_advisor,
            "design": self._score_design,
            "supervisor": self._score_supervisor,
            "vision_interview": self._score_vision_interview,
        }

        for agent_id, scorer in scorers.items():
            try:
                result = scorer(campaign, metrics)
                result["grade"] = _to_grade(result["score"])
                results[agent_id] = result
            except Exception as e:
                logger.error(f"Scoring failed for {agent_id}: {e}")
                results[agent_id] = {"score": 0, "grade": "—", "reasoning": "Scoring error", "metrics": {}}

        return results

    def _score_prospector(self, campaign: Campaign, metrics: dict) -> dict:
        """% of prospects that became meetings. Quality: ICP match accuracy."""
        prospect_count = campaign.memory.prospect_count
        crm = metrics.get("crm_metrics", {})
        meetings = crm.get("total_deals", 0)

        if prospect_count == 0:
            return {"score": 0, "reasoning": "No prospects generated yet", "metrics": {"prospects": 0}}

        # Base score from volume
        volume_score = min(50, prospect_count * 6.25)  # 8 prospects = 50 pts

        # Conversion score
        if meetings > 0:
            conversion_rate = meetings / prospect_count * 100
            conversion_score = min(50, conversion_rate * 5)  # 10% conversion = 50 pts
        else:
            conversion_score = 10  # Base credit for having prospects ready

        score = volume_score + conversion_score
        return {
            "score": min(100, score),
            "reasoning": f"{prospect_count} prospects, {meetings} became meetings ({meetings/prospect_count*100:.0f}% conversion)" if meetings else f"{prospect_count} prospects generated, awaiting meeting data",
            "metrics": {"prospects": prospect_count, "meetings": meetings},
        }

    def _score_outreach(self, campaign: Campaign, metrics: dict) -> dict:
        """Reply rate, positive reply rate, meetings booked per sequence sent."""
        email = metrics.get("email_metrics", {})
        if not email or email.get("delivered", 0) == 0:
            has_sequence = bool(campaign.memory.email_sequence)
            return {"score": 30 if has_sequence else 0,
                    "reasoning": "Sequence written, awaiting send data" if has_sequence else "No outreach sequence yet",
                    "metrics": {}}

        reply_rate = email.get("reply_rate", 0)
        open_rate = email.get("open_rate", 0)

        # Score: open_rate (30pts max) + reply_rate (70pts max)
        open_score = min(30, open_rate * 0.6)  # 50% open = 30 pts
        reply_score = min(70, reply_rate * 14)  # 5% reply = 70 pts

        score = open_score + reply_score
        return {
            "score": min(100, score),
            "reasoning": f"Open rate: {open_rate}%, Reply rate: {reply_rate}%, {email.get('delivered', 0)} delivered",
            "metrics": email,
        }

    def _score_content(self, campaign: Campaign, metrics: dict) -> dict:
        """Organic traffic generated, time on page, leads from content."""
        site = metrics.get("site_metrics", {})
        has_strategy = bool(campaign.memory.content_strategy)

        if not site or site.get("sessions", 0) == 0:
            return {"score": 30 if has_strategy else 0,
                    "reasoning": "Strategy built, awaiting traffic data" if has_strategy else "No content strategy yet",
                    "metrics": {}}

        sessions = site.get("sessions", 0)
        bounce_rate = site.get("bounce_rate", 50)
        conversion_rate = site.get("conversion_rate", 0)

        traffic_score = min(30, sessions / 10)  # 300 sessions = 30 pts
        quality_score = min(35, max(0, (100 - bounce_rate)) * 0.5)  # 30% bounce = 35 pts
        conversion_score = min(35, conversion_rate * 7)  # 5% conversion = 35 pts

        score = traffic_score + quality_score + conversion_score
        return {
            "score": min(100, score),
            "reasoning": f"{sessions} sessions, {bounce_rate}% bounce, {conversion_rate}% conversion",
            "metrics": site,
        }

    def _score_social(self, campaign: Campaign, metrics: dict) -> dict:
        """Engagement rate, follower growth, DM conversations started."""
        social = metrics.get("social_metrics", {})
        has_calendar = bool(campaign.memory.social_calendar)

        if not social or social.get("posts", 0) == 0:
            return {"score": 25 if has_calendar else 0,
                    "reasoning": "Calendar ready, awaiting post data" if has_calendar else "No social calendar yet",
                    "metrics": {}}

        engagement_rate = social.get("engagement_rate", 0)
        followers = social.get("followers_gained", 0)
        dms = social.get("dms_received", 0)

        engagement_score = min(40, engagement_rate * 8)  # 5% engagement = 40 pts
        follower_score = min(30, followers * 0.3)  # 100 followers = 30 pts
        dm_score = min(30, dms * 6)  # 5 DMs = 30 pts

        score = engagement_score + follower_score + dm_score
        return {
            "score": min(100, score),
            "reasoning": f"{engagement_rate}% engagement, {followers} followers gained, {dms} DMs",
            "metrics": social,
        }

    def _score_ads(self, campaign: Campaign, metrics: dict) -> dict:
        """CPA vs target, ROAS, conversion rate."""
        ad = metrics.get("ad_metrics", {})
        has_package = bool(campaign.memory.ad_package)

        if not ad or ad.get("impressions", 0) == 0:
            return {"score": 25 if has_package else 0,
                    "reasoning": "Ad package ready, awaiting performance data" if has_package else "No ad package yet",
                    "metrics": {}}

        ctr = ad.get("ctr", 0)
        roas = ad.get("roas", 0)
        cpa = ad.get("cpa", 999)

        ctr_score = min(30, ctr * 15)  # 2% CTR = 30 pts
        roas_score = min(40, roas * 10)  # 4x ROAS = 40 pts
        cpa_score = min(30, max(0, (200 - cpa)) * 0.15)  # $0 CPA = 30 pts

        score = ctr_score + roas_score + cpa_score
        return {
            "score": min(100, score),
            "reasoning": f"CTR: {ctr}%, ROAS: {roas}x, CPA: ${cpa:.2f}",
            "metrics": ad,
        }

    def _score_cs(self, campaign: Campaign, metrics: dict) -> dict:
        """Client retention rate, upsell rate."""
        has_system = bool(campaign.memory.cs_system)
        crm = metrics.get("crm_metrics", {})
        close_rate = crm.get("close_rate", 0)

        if not has_system:
            return {"score": 0, "reasoning": "No CS system yet", "metrics": {}}

        base = 40  # Having a system built
        retention_score = min(60, close_rate)  # Maps close_rate to retention quality

        return {
            "score": min(100, base + retention_score),
            "reasoning": f"CS system active, {close_rate}% close rate" if close_rate else "CS system built, awaiting client data",
            "metrics": crm,
        }

    def _score_sitelaunch(self, campaign: Campaign, metrics: dict) -> dict:
        has_brief = bool(campaign.memory.site_launch_brief)
        site = metrics.get("site_metrics", {})
        if not has_brief:
            return {"score": 0, "reasoning": "No site brief yet", "metrics": {}}
        if not site:
            return {"score": 30, "reasoning": "Site brief ready, no live traffic data yet", "metrics": {}}
        # Real scoring from live site metrics
        base = 30  # brief exists
        sessions = site.get("sessions", 0)
        bounce_rate = site.get("bounce_rate", 50)
        conversion_rate = site.get("conversion_rate", 0)
        traffic_score = min(20, sessions / 5)  # 100 sessions = 20 pts
        bounce_score = min(25, max(0, (100 - bounce_rate) * 0.5))  # low bounce = high score
        conversion_score = min(25, conversion_rate * 5)  # 5% conversion = 25 pts
        score = base + traffic_score + bounce_score + conversion_score
        return {
            "score": min(100, score),
            "reasoning": f"Site live: {sessions} sessions, {bounce_rate}% bounce, {conversion_rate}% conversion",
            "metrics": site,
        }

    def _score_legal(self, campaign: Campaign, metrics: dict) -> dict:
        has_playbook = bool(campaign.memory.legal_playbook)
        if not has_playbook:
            return {"score": 0, "reasoning": "No legal playbook yet", "metrics": {}}
        # Score based on playbook completeness — count substantive sections
        playbook = campaign.memory.legal_playbook
        sections_present = 0
        key_sections = ["privacy", "terms", "compliance", "contract", "ip", "liability",
                        "incorporation", "gdpr", "employment", "nda"]
        playbook_lower = playbook.lower() if isinstance(playbook, str) else ""
        for section in key_sections:
            if section in playbook_lower:
                sections_present += 1
        coverage_pct = (sections_present / len(key_sections)) * 100
        base = 35  # playbook exists
        depth_score = min(35, len(playbook) / 100) if isinstance(playbook, str) else 0  # longer = more thorough
        coverage_score = min(30, sections_present * 3)
        score = base + depth_score + coverage_score
        return {
            "score": min(100, score),
            "reasoning": f"Legal playbook covers {sections_present}/{len(key_sections)} key areas ({coverage_pct:.0f}% coverage)",
            "metrics": {"sections_covered": sections_present, "total_sections": len(key_sections),
                        "coverage_pct": coverage_pct, "playbook_length": len(playbook) if isinstance(playbook, str) else 0},
        }

    def _score_marketing_expert(self, campaign: Campaign, metrics: dict) -> dict:
        has_strategy = bool(campaign.memory.gtm_strategy)
        if not has_strategy:
            return {"score": 0, "reasoning": "No GTM strategy yet", "metrics": {}}
        # Score strategy quality by checking for key GTM components
        strategy = campaign.memory.gtm_strategy
        strategy_lower = strategy.lower() if isinstance(strategy, str) else ""
        components = ["icp", "positioning", "pricing", "channel", "messaging",
                      "competitor", "timeline", "metric", "budget", "launch"]
        components_found = sum(1 for c in components if c in strategy_lower)
        # Check if strategy references real campaign data
        has_data_refs = any(kw in strategy_lower for kw in ["conversion", "revenue", "pipeline", "growth", "roi"])
        base = 30
        component_score = min(40, components_found * 4)
        depth_score = min(20, len(strategy) / 150) if isinstance(strategy, str) else 0
        data_bonus = 10 if has_data_refs else 0
        score = base + component_score + depth_score + data_bonus
        return {
            "score": min(100, score),
            "reasoning": f"GTM strategy covers {components_found}/{len(components)} components, {'data-informed' if has_data_refs else 'needs data validation'}",
            "metrics": {"components_covered": components_found, "total_components": len(components),
                        "data_informed": has_data_refs, "strategy_length": len(strategy) if isinstance(strategy, str) else 0},
        }

    def _score_procurement(self, campaign: Campaign, metrics: dict) -> dict:
        has_stack = bool(campaign.memory.tool_stack)
        if not has_stack:
            return {"score": 0, "reasoning": "No tool stack yet", "metrics": {}}
        # Score tool stack by counting tools, categories, and integration depth
        stack = campaign.memory.tool_stack
        stack_lower = stack.lower() if isinstance(stack, str) else ""
        categories = ["crm", "email", "analytics", "payment", "hosting", "social",
                      "advertising", "seo", "design", "communication"]
        categories_covered = sum(1 for c in categories if c in stack_lower)
        # Check for cost analysis
        has_costs = any(kw in stack_lower for kw in ["$", "cost", "pricing", "free", "month"])
        has_alternatives = any(kw in stack_lower for kw in ["alternative", "vs", "compare", "option"])
        base = 30
        category_score = min(35, categories_covered * 3.5)
        cost_score = 15 if has_costs else 0
        alt_score = 10 if has_alternatives else 0
        depth_score = min(10, len(stack) / 200) if isinstance(stack, str) else 0
        score = base + category_score + cost_score + alt_score + depth_score
        return {
            "score": min(100, score),
            "reasoning": f"Tool stack covers {categories_covered}/{len(categories)} categories, {'with cost analysis' if has_costs else 'needs cost analysis'}",
            "metrics": {"categories_covered": categories_covered, "total_categories": len(categories),
                        "has_cost_analysis": has_costs, "has_alternatives": has_alternatives},
        }

    def _score_newsletter(self, campaign: Campaign, metrics: dict) -> dict:
        has_system = bool(campaign.memory.newsletter_system)
        email = metrics.get("email_metrics", {})
        open_rate = email.get("open_rate", 0)
        if not has_system:
            return {"score": 0, "reasoning": "No newsletter system yet", "metrics": {}}
        base = 40
        performance = min(60, open_rate * 1.5)
        return {"score": min(100, base + performance),
                "reasoning": f"Newsletter active, {open_rate}% open rate" if open_rate else "Newsletter system ready",
                "metrics": email}

    def _score_ppc(self, campaign: Campaign, metrics: dict) -> dict:
        has_playbook = bool(campaign.memory.ppc_playbook)
        ad = metrics.get("ad_metrics", {})
        if not has_playbook:
            return {"score": 0, "reasoning": "No PPC playbook yet", "metrics": {}}
        roas = ad.get("roas", 0)
        base = 35
        perf = min(65, roas * 16) if roas else 0
        return {"score": min(100, base + perf),
                "reasoning": f"PPC optimizing, ROAS: {roas}x" if roas else "PPC playbook ready",
                "metrics": ad}


    # ── Back-Office Agents ──────────────────────────────────────────

    def _score_finance(self, campaign: Campaign, metrics: dict) -> dict:
        """P&L accuracy, cash-flow visibility, budget adherence."""
        has_plan = bool(campaign.memory.financial_plan)
        fin = metrics.get("finance_metrics", {})

        if not has_plan:
            return {"score": 0, "reasoning": "No financial plan yet", "metrics": {}}

        base = 40  # Plan exists
        revenue = fin.get("mrr", 0) or fin.get("total_revenue", 0)
        burn = fin.get("monthly_burn", 0)

        runway_score = 0
        if burn > 0 and revenue > 0:
            ratio = revenue / burn
            runway_score = min(30, ratio * 15)  # 2x revenue/burn = 30 pts

        accuracy_score = min(30, fin.get("forecast_accuracy", 0) * 0.3)  # 100% accuracy = 30 pts

        score = base + runway_score + accuracy_score
        return {
            "score": min(100, score),
            "reasoning": f"Financial plan active, rev/burn ratio: {revenue/burn:.1f}x" if burn > 0 else "Financial plan built, awaiting revenue data",
            "metrics": fin,
        }

    def _score_hr(self, campaign: Campaign, metrics: dict) -> dict:
        """Hiring velocity, compliance coverage, team fill rate."""
        has_playbook = bool(campaign.memory.hr_playbook)
        hr = metrics.get("hr_metrics", {})

        if not has_playbook:
            return {"score": 0, "reasoning": "No HR playbook yet", "metrics": {}}

        base = 40
        positions_filled = hr.get("positions_filled", 0)
        positions_open = hr.get("positions_open", 0)
        total = positions_filled + positions_open

        fill_score = 0
        if total > 0:
            fill_score = min(35, (positions_filled / total) * 35)

        compliance_score = min(25, hr.get("compliance_pct", 0) * 0.25)  # 100% = 25 pts

        score = base + fill_score + compliance_score
        return {
            "score": min(100, score),
            "reasoning": f"HR active, {positions_filled}/{total} positions filled" if total else "HR playbook ready, awaiting hiring data",
            "metrics": hr,
        }

    def _score_sales(self, campaign: Campaign, metrics: dict) -> dict:
        """Pipeline value, close rate, average deal size."""
        has_playbook = bool(campaign.memory.sales_playbook)
        crm = metrics.get("crm_metrics", {})

        if not has_playbook:
            return {"score": 0, "reasoning": "No sales playbook yet", "metrics": {}}

        base = 35
        close_rate = crm.get("close_rate", 0)
        pipeline_value = crm.get("pipeline_value", 0)
        deals = crm.get("total_deals", 0)

        close_score = min(30, close_rate * 1.2)  # 25% close = 30 pts
        pipeline_score = min(20, pipeline_value / 5000)  # $100K pipeline = 20 pts
        volume_score = min(15, deals * 1.5)  # 10 deals = 15 pts

        score = base + close_score + pipeline_score + volume_score
        return {
            "score": min(100, score),
            "reasoning": f"Pipeline: ${pipeline_value:,.0f}, {close_rate}% close rate, {deals} deals" if deals else "Sales playbook ready, awaiting pipeline data",
            "metrics": crm,
        }

    def _score_delivery(self, campaign: Campaign, metrics: dict) -> dict:
        """On-time delivery rate, client satisfaction, capacity utilization."""
        has_system = bool(campaign.memory.delivery_system)
        ops = metrics.get("delivery_metrics", {})

        if not has_system:
            return {"score": 0, "reasoning": "No delivery system yet", "metrics": {}}

        base = 40
        on_time = ops.get("on_time_pct", 0)
        satisfaction = ops.get("csat", 0)
        utilization = ops.get("utilization_pct", 0)

        ontime_score = min(25, on_time * 0.25)  # 100% on-time = 25 pts
        csat_score = min(20, satisfaction * 4)  # 5.0 CSAT = 20 pts
        util_score = min(15, utilization * 0.15)  # 100% util = 15 pts (over-utilization penalized by cap)

        score = base + ontime_score + csat_score + util_score
        return {
            "score": min(100, score),
            "reasoning": f"Delivery active, {on_time}% on-time, {satisfaction}/5 CSAT" if on_time else "Delivery system built, awaiting ops data",
            "metrics": ops,
        }

    def _score_analytics(self, campaign: Campaign, metrics: dict) -> dict:
        """Dashboard coverage, insight actionability, data freshness."""
        has_framework = bool(campaign.memory.analytics_framework)

        if not has_framework:
            return {"score": 0, "reasoning": "No analytics framework yet", "metrics": {}}

        # Score based on how many metric sources are feeding in
        sources_active = sum(1 for k in ["email_metrics", "ad_metrics", "site_metrics",
                                          "social_metrics", "crm_metrics", "finance_metrics"]
                             if metrics.get(k))

        base = 40
        coverage_score = min(40, sources_active * 8)  # 5 sources = 40 pts
        # Extra credit if key metrics are present
        has_attribution = 1 if metrics.get("attribution_model") else 0
        has_dashboard = 1 if metrics.get("dashboard_live") else 0
        bonus = (has_attribution + has_dashboard) * 10

        score = base + coverage_score + bonus
        return {
            "score": min(100, score),
            "reasoning": f"Analytics framework active, {sources_active}/6 data sources connected",
            "metrics": {"sources_active": sources_active},
        }

    def _score_tax(self, campaign: Campaign, metrics: dict) -> dict:
        """Tax savings identified, compliance status, deadline adherence."""
        has_playbook = bool(campaign.memory.tax_playbook)
        tax = metrics.get("tax_metrics", {})

        if not has_playbook:
            return {"score": 0, "reasoning": "No tax playbook yet", "metrics": {}}

        base = 45  # Tax planning alone is high-value
        savings = tax.get("annual_savings", 0)
        compliance = tax.get("compliance_pct", 100)

        savings_score = min(30, savings / 1000)  # $30K savings = 30 pts
        compliance_score = min(25, compliance * 0.25)  # 100% compliance = 25 pts

        score = base + savings_score + compliance_score
        return {
            "score": min(100, score),
            "reasoning": f"Tax strategy active, ${savings:,.0f} annual savings identified, {compliance}% compliant" if savings else "Tax playbook built, awaiting filing data",
            "metrics": tax,
        }

    def _score_wealth(self, campaign: Campaign, metrics: dict) -> dict:
        """Wealth structures deployed, asset protection coverage, tax efficiency."""
        has_strategy = bool(campaign.memory.wealth_strategy)
        wealth = metrics.get("wealth_metrics", {})

        if not has_strategy:
            return {"score": 0, "reasoning": "No wealth strategy yet", "metrics": {}}

        base = 45
        structures = wealth.get("structures_deployed", 0)
        protection_pct = wealth.get("asset_protection_pct", 0)

        structure_score = min(30, structures * 10)  # 3 structures = 30 pts
        protection_score = min(25, protection_pct * 0.25)  # 100% = 25 pts

        score = base + structure_score + protection_score
        return {
            "score": min(100, score),
            "reasoning": f"Wealth strategy active, {structures} structures, {protection_pct}% asset protection" if structures else "Wealth strategy built, awaiting implementation data",
            "metrics": wealth,
        }


    # ── Revenue Multiplier Agents ─────────────────────────────────────

    def _score_billing(self, campaign: Campaign, metrics: dict) -> dict:
        """Collection rate, DSO, MRR accuracy, dunning effectiveness."""
        has_system = bool(campaign.memory.billing_system)
        rev = metrics.get("revenue_metrics", {})
        billing = metrics.get("billing_metrics", {})

        if not has_system:
            return {"score": 0, "reasoning": "No billing system yet", "metrics": {}}

        base = 40
        collection_rate = billing.get("collection_rate", 0) or rev.get("collection_rate", 0)
        mrr = rev.get("mrr", 0)

        collection_score = min(30, collection_rate * 0.3)  # 100% collection = 30 pts
        revenue_score = min(30, mrr / 500)  # $15K MRR = 30 pts

        score = base + collection_score + revenue_score
        return {
            "score": min(100, score),
            "reasoning": f"Billing active, {collection_rate}% collection rate, ${mrr:,.0f} MRR" if mrr else "Billing system built, awaiting payment data",
            "metrics": {**rev, **billing},
        }

    def _score_referral(self, campaign: Campaign, metrics: dict) -> dict:
        """Active affiliates, referral conversion rate, referral revenue %."""
        has_program = bool(campaign.memory.referral_program)
        ref = metrics.get("referral_metrics", {})

        if not has_program:
            return {"score": 0, "reasoning": "No referral program yet", "metrics": {}}

        base = 35
        affiliates = ref.get("active_affiliates", 0)
        referrals = ref.get("total_referrals", 0)
        revenue = ref.get("total_revenue", 0)

        affiliate_score = min(25, affiliates * 5)  # 5 active = 25 pts
        referral_score = min(20, referrals * 2)  # 10 referrals = 20 pts
        revenue_score = min(20, revenue / 500)  # $10K revenue = 20 pts

        score = base + affiliate_score + referral_score + revenue_score
        return {
            "score": min(100, score),
            "reasoning": f"Referral program active, {affiliates} affiliates, {referrals} referrals, ${revenue:,.0f} attributed" if affiliates else "Referral program built, recruiting partners",
            "metrics": ref,
        }

    def _score_portfolio_ops(self, campaign: Campaign, metrics: dict) -> dict:
        """Portfolio health, cross-campaign learning utilization, template coverage."""
        # Portfolio ops is scored on genome utilization + campaign count
        has_genome = bool(campaign.memory.genome_intel)
        portfolio = metrics.get("portfolio_metrics", {})

        base = 40 if has_genome else 20
        campaigns_managed = portfolio.get("total_campaigns", 1)
        templates_used = portfolio.get("templates_used", 0)

        campaign_score = min(30, campaigns_managed * 10)  # 3 campaigns = 30 pts
        template_score = min(30, templates_used * 15)  # 2 templates = 30 pts

        score = base + campaign_score + template_score
        return {
            "score": min(100, score),
            "reasoning": f"Managing {campaigns_managed} campaigns, genome intelligence active" if has_genome else "Portfolio ops initialized, awaiting multi-campaign data",
            "metrics": portfolio,
        }


    # ── Differentiation Agents ──────────────────────────────────────

    def _score_competitive_intel(self, campaign: Campaign, metrics: dict) -> dict:
        """Competitor coverage, insight freshness, actionable recommendations."""
        has_intel = bool(campaign.memory.competitive_intel)
        if not has_intel:
            return {"score": 0, "reasoning": "No competitive intelligence yet", "metrics": {}}
        intel = campaign.memory.competitive_intel
        intel_lower = intel.lower() if isinstance(intel, str) else ""
        # Score by depth of competitive analysis
        dimensions = ["pricing", "feature", "strength", "weakness", "positioning",
                      "market share", "differentiat", "threat", "opportunity", "swot"]
        dimensions_covered = sum(1 for d in dimensions if d in intel_lower)
        competitors_mentioned = intel_lower.count("competitor") + intel_lower.count(" vs ")
        has_actionable = any(kw in intel_lower for kw in ["recommend", "action", "strategy", "counter", "advantage"])
        base = 30
        dimension_score = min(30, dimensions_covered * 3)
        depth_score = min(20, len(intel) / 150) if isinstance(intel, str) else 0
        action_score = 10 if has_actionable else 0
        competitor_score = min(10, competitors_mentioned * 2)
        score = base + dimension_score + depth_score + action_score + competitor_score
        return {
            "score": min(100, score),
            "reasoning": f"Competitive intel covers {dimensions_covered} dimensions, {'actionable' if has_actionable else 'needs action items'}",
            "metrics": {"dimensions_covered": dimensions_covered, "competitors_analyzed": competitors_mentioned,
                        "has_actionable_recommendations": has_actionable},
        }

    def _score_client_portal(self, campaign: Campaign, metrics: dict) -> dict:
        """Dashboard completeness, report automation, client satisfaction."""
        has_portal = bool(campaign.memory.client_portal)
        if not has_portal:
            return {"score": 0, "reasoning": "No client portal spec yet", "metrics": {}}
        portal = campaign.memory.client_portal
        portal_lower = portal.lower() if isinstance(portal, str) else ""
        # Score by portal feature completeness
        features = ["dashboard", "report", "metric", "chart", "notification",
                     "permission", "export", "automation", "template", "branding"]
        features_present = sum(1 for f in features if f in portal_lower)
        has_real_time = any(kw in portal_lower for kw in ["real-time", "live", "websocket", "streaming"])
        has_self_serve = any(kw in portal_lower for kw in ["self-serve", "self-service", "customize", "configur"])
        base = 25
        feature_score = min(35, features_present * 3.5)
        depth_score = min(20, len(portal) / 150) if isinstance(portal, str) else 0
        realtime_bonus = 10 if has_real_time else 0
        selfserve_bonus = 10 if has_self_serve else 0
        score = base + feature_score + depth_score + realtime_bonus + selfserve_bonus
        return {
            "score": min(100, score),
            "reasoning": f"Portal spec covers {features_present}/{len(features)} features, {'real-time' if has_real_time else 'batch'} data",
            "metrics": {"features_present": features_present, "total_features": len(features),
                        "has_real_time": has_real_time, "has_self_service": has_self_serve},
        }

    def _score_voice_receptionist(self, campaign: Campaign, metrics: dict) -> dict:
        """Call handling rate, qualification accuracy, booking conversion."""
        has_system = bool(campaign.memory.voice_receptionist)
        voice = metrics.get("voice_metrics", {})
        if not has_system:
            return {"score": 0, "reasoning": "No voice receptionist yet", "metrics": {}}
        calls = voice.get("calls_handled", 0)
        meetings = voice.get("meetings_booked", 0)
        base = 45
        call_score = min(25, calls * 2.5)
        booking_score = min(30, meetings * 10) if calls > 0 else 0
        score = base + call_score + booking_score
        return {
            "score": min(100, score),
            "reasoning": f"Voice AI active, {calls} calls handled, {meetings} meetings booked" if calls else "Voice receptionist system configured",
            "metrics": voice,
        }


    # ── Communications & Partnerships ────────────────────────────

    def _score_pr_comms(self, campaign: Campaign, metrics: dict) -> dict:
        """Media placements, share of voice, crisis readiness."""
        has_output = bool(campaign.memory.pr_communications)
        pr = metrics.get("pr_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No PR/communications strategy yet", "metrics": {}}
        base = 40
        placements = pr.get("media_placements", 0)
        mentions = pr.get("brand_mentions", 0)
        placement_score = min(30, placements * 6)  # 5 placements = 30 pts
        mention_score = min(30, mentions * 3)  # 10 mentions = 30 pts
        score = base + placement_score + mention_score
        return {
            "score": min(100, score),
            "reasoning": f"PR active, {placements} media placements, {mentions} brand mentions" if placements else "PR strategy built, media outreach initiated",
            "metrics": pr,
        }

    def _score_data_engineer(self, campaign: Campaign, metrics: dict) -> dict:
        """Dashboard coverage, data freshness, alert accuracy."""
        has_output = bool(campaign.memory.data_dashboards)
        data = metrics.get("data_eng_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No data dashboards yet", "metrics": {}}
        base = 45
        dashboards = data.get("dashboards_live", 0)
        pipelines = data.get("etl_pipelines_active", 0)
        dash_score = min(25, dashboards * 12)  # 2 dashboards = 24 pts
        pipe_score = min(30, pipelines * 6)  # 5 pipelines = 30 pts
        score = base + dash_score + pipe_score
        return {
            "score": min(100, score),
            "reasoning": f"Data layer active, {dashboards} dashboards, {pipelines} ETL pipelines" if dashboards else "Dashboard specs complete, awaiting deployment",
            "metrics": data,
        }

    def _score_governance(self, campaign: Campaign, metrics: dict) -> dict:
        """Compliance rate, audit readiness, regulatory coverage."""
        has_output = bool(campaign.memory.governance_brief)
        gov = metrics.get("governance_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No governance framework yet", "metrics": {}}
        base = 50  # Governance is inherently high-value
        compliance_pct = gov.get("compliance_rate", 0)
        filings_on_time = gov.get("filings_on_time_pct", 0)
        compliance_score = min(25, compliance_pct * 0.25)
        filing_score = min(25, filings_on_time * 0.25)
        score = base + compliance_score + filing_score
        return {
            "score": min(100, score),
            "reasoning": f"Governance active, {compliance_pct}% compliant, {filings_on_time}% filings on-time" if compliance_pct else "Governance framework established, monitoring active",
            "metrics": gov,
        }

    def _score_product_manager(self, campaign: Campaign, metrics: dict) -> dict:
        """Roadmap coverage, feature delivery rate, backlog health."""
        has_output = bool(campaign.memory.product_roadmap)
        pm = metrics.get("product_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No product roadmap yet", "metrics": {}}
        base = 40
        features_shipped = pm.get("features_shipped", 0)
        backlog_groomed = pm.get("backlog_groomed_pct", 0)
        feature_score = min(30, features_shipped * 6)  # 5 features = 30 pts
        backlog_score = min(30, backlog_groomed * 0.3)  # 100% groomed = 30 pts
        score = base + feature_score + backlog_score
        return {
            "score": min(100, score),
            "reasoning": f"Product active, {features_shipped} features shipped, {backlog_groomed}% backlog groomed" if features_shipped else "Product roadmap built, sprint planning active",
            "metrics": pm,
        }

    def _score_partnerships(self, campaign: Campaign, metrics: dict) -> dict:
        """Active partnerships, UGC volume, industry influence score."""
        has_output = bool(campaign.memory.partnerships_playbook)
        bd = metrics.get("partnership_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No partnerships strategy yet", "metrics": {}}
        base = 35
        active_partners = bd.get("active_partnerships", 0)
        ugc_pieces = bd.get("ugc_content_pieces", 0)
        partner_revenue = bd.get("partner_attributed_revenue", 0)
        partner_score = min(25, active_partners * 5)
        ugc_score = min(20, ugc_pieces * 2)
        revenue_score = min(20, partner_revenue / 500)
        score = base + partner_score + ugc_score + revenue_score
        return {
            "score": min(100, score),
            "reasoning": f"BD active, {active_partners} partners, {ugc_pieces} UGC pieces, ${partner_revenue:,.0f} attributed" if active_partners else "Partnership strategy built, outreach initiated",
            "metrics": bd,
        }

    # ── Builder & Intelligence Agents ──────────────────────────────

    def _score_fullstack_dev(self, campaign: Campaign, metrics: dict) -> dict:
        """Code quality, deployment readiness, test coverage, security audit pass rate."""
        has_output = bool(campaign.memory.fullstack_dev_output)
        dev = metrics.get("dev_metrics", {})

        if not has_output:
            return {"score": 0, "reasoning": "No full-stack dev output yet", "metrics": {}}

        base = 45  # Having a production-ready app blueprint is high-value
        test_coverage = dev.get("test_coverage_pct", 0)
        security_score = dev.get("security_audit_score", 0)
        deployed = 1 if dev.get("deployed") else 0

        test_score = min(20, test_coverage * 0.2)  # 100% coverage = 20 pts
        security_pts = min(20, security_score * 0.2)  # 100 score = 20 pts
        deploy_score = 15 if deployed else 0

        score = base + test_score + security_pts + deploy_score
        return {
            "score": min(100, score),
            "reasoning": f"App built, {test_coverage}% test coverage, security {security_score}/100, {'deployed' if deployed else 'ready to deploy'}" if test_coverage else "Full-stack blueprint complete, awaiting build metrics",
            "metrics": dev,
        }

    def _score_economist(self, campaign: Campaign, metrics: dict) -> dict:
        """Intelligence freshness, actionable insights count, risk accuracy."""
        has_briefing = bool(campaign.memory.economist_briefing)
        econ = metrics.get("economist_metrics", {})

        if not has_briefing:
            return {"score": 0, "reasoning": "No economist briefing yet", "metrics": {}}

        base = 50  # Economic intelligence is inherently valuable
        insights_actioned = econ.get("insights_actioned", 0)
        risks_flagged = econ.get("risks_flagged", 0)
        accuracy = econ.get("prediction_accuracy_pct", 0)

        insight_score = min(20, insights_actioned * 5)  # 4 actioned = 20 pts
        risk_score = min(15, risks_flagged * 3)  # 5 risks flagged = 15 pts
        accuracy_score = min(15, accuracy * 0.15)  # 100% accuracy = 15 pts

        score = base + insight_score + risk_score + accuracy_score
        return {
            "score": min(100, score),
            "reasoning": f"Economic briefing active, {insights_actioned} insights actioned, {risks_flagged} risks flagged" if insights_actioned else "Economic intelligence briefing complete, monitoring active",
            "metrics": econ,
        }


    # ── Client Layer & Cognition Agents ──────────────────────────

    def _score_client_fulfillment(self, campaign: Campaign, metrics: dict) -> dict:
        """Client activation rate, time-to-value, CSAT, retention."""
        has_output = bool(campaign.memory.client_fulfillment)
        ful = metrics.get("fulfillment_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No client fulfillment system yet", "metrics": {}}
        base = 45
        activation_rate = ful.get("activation_rate_pct", 0)
        ttv_days = ful.get("time_to_value_days", 0)
        retention = ful.get("retention_rate_pct", 0)
        activation_score = min(20, activation_rate * 0.2)
        ttv_score = min(15, max(0, 15 - ttv_days))  # lower TTv = higher score
        retention_score = min(20, retention * 0.2)
        score = base + activation_score + ttv_score + retention_score
        return {
            "score": min(100, score),
            "reasoning": f"Fulfillment active, {activation_rate}% activation, {ttv_days}d time-to-value, {retention}% retention" if activation_rate else "Client fulfillment system built, awaiting client data",
            "metrics": ful,
        }

    def _score_knowledge_engine(self, campaign: Campaign, metrics: dict) -> dict:
        """Knowledge coverage, query success rate, self-sufficiency score."""
        # knowledge_engine doesn't have its own memory field — it enriches the entire system
        kb = metrics.get("knowledge_metrics", {})
        coverage = kb.get("knowledge_coverage_pct", 0)
        queries_internal = kb.get("queries_served_internally_pct", 0)
        base = 30 if coverage > 0 else 15
        coverage_score = min(35, coverage * 0.35)
        internal_score = min(35, queries_internal * 0.35)
        score = base + coverage_score + internal_score
        return {
            "score": min(100, score),
            "reasoning": f"Knowledge engine active, {coverage}% domain coverage, {queries_internal}% queries self-served" if coverage else "Knowledge engine initializing, accumulating data",
            "metrics": kb,
        }

    def _score_agent_ops(self, campaign: Campaign, metrics: dict) -> dict:
        """Workspace uptime, workflow success rate, autonomy level."""
        has_output = bool(campaign.memory.agent_workspace)
        ops = metrics.get("agent_ops_metrics", {})
        if not has_output:
            return {"score": 0, "reasoning": "No agent workspace configured yet", "metrics": {}}
        base = 40
        workflows_active = ops.get("workflows_active", 0)
        success_rate = ops.get("workflow_success_rate_pct", 0)
        wf_score = min(30, workflows_active * 6)
        success_score = min(30, success_rate * 0.3)
        score = base + wf_score + success_score
        return {
            "score": min(100, score),
            "reasoning": f"Agent ops active, {workflows_active} workflows, {success_rate}% success rate" if workflows_active else "Agent workspace architecture configured",
            "metrics": ops,
        }

    def _score_world_model(self, campaign: Campaign, metrics: dict) -> dict:
        """World state freshness, scenario accuracy, social climate coverage."""
        wm = metrics.get("world_model_metrics", {})
        freshness = wm.get("world_state_freshness_hours", 999)
        scenarios = wm.get("scenarios_modeled", 0)
        base = 35
        freshness_score = min(30, max(0, 30 - freshness))  # fresher = higher
        scenario_score = min(35, scenarios * 7)
        score = base + freshness_score + scenario_score
        return {
            "score": min(100, score),
            "reasoning": f"World model active, {freshness}hr freshness, {scenarios} scenarios modeled" if scenarios else "World model initialized, building spatial/temporal/social awareness",
            "metrics": wm,
        }


    def _score_formation(self, campaign: Campaign, metrics: dict) -> dict:
        """Entity formed, EIN obtained, bank account opened, compliance filed."""
        fm = metrics.get("formation_metrics", {})
        entity_formed = fm.get("entity_formed", False)
        ein_obtained = fm.get("ein_obtained", False)
        bank_opened = fm.get("bank_account_opened", False)
        if not entity_formed:
            return {"score": 0, "reasoning": "Business entity not yet formed", "metrics": {}}
        base = 40
        ein_score = 25 if ein_obtained else 0
        bank_score = 20 if bank_opened else 0
        compliance = min(15, fm.get("compliance_filings", 0) * 5)
        score = base + ein_score + bank_score + compliance
        return {
            "score": min(100, score),
            "reasoning": f"Entity formed, EIN {'obtained' if ein_obtained else 'pending'}, bank {'opened' if bank_opened else 'pending'}",
            "metrics": fm,
        }

    def _score_advisor(self, campaign: Campaign, metrics: dict) -> dict:
        """Strategy adoption rate, recommendation actionability."""
        adv = metrics.get("advisor_metrics", {})
        recommendations = adv.get("recommendations_given", 0)
        adopted = adv.get("recommendations_adopted", 0)
        if not recommendations:
            return {"score": 0, "reasoning": "No advisory recommendations yet", "metrics": {}}
        adoption_rate = (adopted / recommendations * 100) if recommendations else 0
        base = 35
        adoption_score = min(40, adoption_rate * 0.4)
        depth = min(25, recommendations * 5)
        score = base + adoption_score + depth
        return {
            "score": min(100, score),
            "reasoning": f"{recommendations} recommendations, {adoption_rate:.0f}% adoption rate",
            "metrics": adv,
        }

    def _score_design(self, campaign: Campaign, metrics: dict) -> dict:
        """Brand assets generated, design consistency, approval rate."""
        ds = metrics.get("design_metrics", {})
        assets = ds.get("assets_generated", 0)
        if not assets:
            return {"score": 0, "reasoning": "No design assets generated yet", "metrics": {}}
        base = 35
        asset_score = min(30, assets * 5)
        consistency = min(20, ds.get("consistency_score_pct", 0) * 0.2)
        approval = min(15, ds.get("approval_rate_pct", 0) * 0.15)
        score = base + asset_score + consistency + approval
        return {
            "score": min(100, score),
            "reasoning": f"{assets} assets generated, design system {'active' if assets > 3 else 'building'}",
            "metrics": ds,
        }

    def _score_supervisor(self, campaign: Campaign, metrics: dict) -> dict:
        """Campaign completion %, agent orchestration efficiency."""
        sup = metrics.get("supervisor_metrics", {})
        agents_run = sup.get("agents_completed", 0)
        agents_total = sup.get("agents_total", 1)
        errors = sup.get("agent_errors", 0)
        completion_pct = (agents_run / agents_total * 100) if agents_total else 0
        base = 30
        completion_score = min(40, completion_pct * 0.4)
        error_penalty = min(20, errors * 5)
        efficiency = min(30, sup.get("avg_iterations_per_agent", 15) / 15 * 30)
        score = base + completion_score - error_penalty + (30 - efficiency)
        return {
            "score": max(0, min(100, score)),
            "reasoning": f"{agents_run}/{agents_total} agents completed, {errors} errors",
            "metrics": sup,
        }

    def _score_vision_interview(self, campaign: Campaign, metrics: dict) -> dict:
        """Business profile completeness, goal clarity."""
        biz = campaign.memory.business
        fields_filled = sum(1 for v in [biz.name, biz.description, biz.industry,
                                         biz.audience, biz.service, biz.url] if v)
        total_fields = 6
        completeness = fields_filled / total_fields * 100
        base = 20
        profile_score = min(60, completeness * 0.6)
        has_goals = 20 if (biz.description and len(biz.description) > 50) else 0
        score = base + profile_score + has_goals
        return {
            "score": min(100, score),
            "reasoning": f"Business profile {completeness:.0f}% complete ({fields_filled}/{total_fields} fields)",
            "metrics": {"fields_filled": fields_filled, "total_fields": total_fields},
        }


scorer = AgentScorer()
