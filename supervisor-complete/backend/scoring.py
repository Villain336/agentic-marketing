"""
Supervisor Backend — Agent Performance Scoring
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
        return {
            "score": 50 if has_brief and not site else min(100, 50 + site.get("conversion_rate", 0) * 10) if site else (30 if has_brief else 0),
            "reasoning": "Site launched with live metrics" if site else ("Site brief ready" if has_brief else "No site brief yet"),
            "metrics": site,
        }

    def _score_legal(self, campaign: Campaign, metrics: dict) -> dict:
        has_playbook = bool(campaign.memory.legal_playbook)
        return {"score": 70 if has_playbook else 0,
                "reasoning": "Legal playbook complete" if has_playbook else "No legal playbook yet",
                "metrics": {}}

    def _score_marketing_expert(self, campaign: Campaign, metrics: dict) -> dict:
        has_strategy = bool(campaign.memory.gtm_strategy)
        return {"score": 70 if has_strategy else 0,
                "reasoning": "GTM strategy built" if has_strategy else "No GTM strategy yet",
                "metrics": {}}

    def _score_procurement(self, campaign: Campaign, metrics: dict) -> dict:
        has_stack = bool(campaign.memory.tool_stack)
        return {"score": 70 if has_stack else 0,
                "reasoning": "Tool stack defined" if has_stack else "No tool stack yet",
                "metrics": {}}

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


scorer = AgentScorer()
