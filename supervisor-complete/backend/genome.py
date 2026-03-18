"""
Supervisor Backend — Campaign Genome
Cross-campaign intelligence: stores structured campaign DNA,
queries similar campaigns, and generates data-driven recommendations.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Optional

from models import Campaign, CampaignMemory

logger = logging.getLogger("supervisor.genome")


class CampaignDNA:
    """Structured fingerprint of a campaign's characteristics and outcomes."""

    def __init__(
        self,
        campaign_id: str,
        icp_type: str = "",
        service_type: str = "",
        geography: str = "",
        entity_type: str = "",
        industry: str = "",
        channel_mix: dict[str, bool] | None = None,
        messaging_angles: list[str] | None = None,
        outcomes: dict[str, float] | None = None,
        lessons: dict[str, list[str]] | None = None,
        created_at: datetime | None = None,
    ):
        self.campaign_id = campaign_id
        self.icp_type = icp_type
        self.service_type = service_type
        self.geography = geography
        self.entity_type = entity_type
        self.industry = industry
        self.channel_mix = channel_mix or {}
        self.messaging_angles = messaging_angles or []
        self.outcomes = outcomes or {}
        self.lessons = lessons or {"what_worked": [], "what_didnt": []}
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "icp_type": self.icp_type,
            "service_type": self.service_type,
            "geography": self.geography,
            "entity_type": self.entity_type,
            "industry": self.industry,
            "channel_mix": self.channel_mix,
            "messaging_angles": self.messaging_angles,
            "outcomes": self.outcomes,
            "lessons": self.lessons,
            "created_at": self.created_at.isoformat(),
        }

    def similarity_score(self, icp_type: str = "", service_type: str = "", geography: str = "", industry: str = "") -> float:
        """Score 0-1 how similar this DNA is to the query criteria."""
        score = 0.0
        checks = 0

        if icp_type:
            checks += 1
            if self.icp_type and icp_type.lower() in self.icp_type.lower():
                score += 1.0
            elif self.icp_type and any(w in self.icp_type.lower() for w in icp_type.lower().split()):
                score += 0.5

        if service_type:
            checks += 1
            if self.service_type and service_type.lower() in self.service_type.lower():
                score += 1.0
            elif self.service_type and any(w in self.service_type.lower() for w in service_type.lower().split()):
                score += 0.5

        if geography:
            checks += 1
            if self.geography and geography.lower() in self.geography.lower():
                score += 1.0

        if industry:
            checks += 1
            if self.industry and industry.lower() in self.industry.lower():
                score += 1.0
            elif self.industry and any(w in self.industry.lower() for w in industry.lower().split()):
                score += 0.5

        return score / checks if checks > 0 else 0.0


class CampaignGenome:
    """Stores and queries structured campaign intelligence across all users."""

    def __init__(self):
        self._dna_store: dict[str, CampaignDNA] = {}

    def record_campaign_dna(self, campaign: Campaign, metrics: dict[str, Any] | None = None) -> CampaignDNA:
        """Extract campaign DNA from a completed (or running) campaign."""
        mem = campaign.memory
        biz = mem.business

        channel_mix = {
            "outreach": bool(mem.email_sequence),
            "content": bool(mem.content_strategy),
            "social": bool(mem.social_calendar),
            "ads": bool(mem.ad_package),
            "newsletter": bool(mem.newsletter_system),
            "ppc": bool(mem.ppc_playbook),
            "site": bool(mem.site_launch_brief),
        }

        # Extract messaging angles from available outputs
        angles = []
        if mem.gtm_strategy:
            angles.append("gtm_strategy")
        if mem.email_sequence:
            angles.append("cold_outreach")
        if mem.content_strategy:
            angles.append("content_marketing")
        if mem.social_calendar:
            angles.append("social_media")
        if mem.ad_package:
            angles.append("paid_ads")

        # Build outcomes from metrics if available
        outcomes = {}
        if metrics:
            for key in ["reply_rate", "open_rate", "ctr", "cpa", "roas",
                        "conversion_rate", "bounce_rate", "close_rate",
                        "engagement_rate", "follower_growth", "mrr", "total_revenue"]:
                if key in metrics:
                    outcomes[key] = metrics[key]

        # Extract lessons from agent scores if available
        lessons: dict[str, list[str]] = {"what_worked": [], "what_didnt": []}
        if metrics:
            for agent_id, data in metrics.get("agent_scores", {}).items():
                grade = data.get("grade", "")
                if grade in ("A+", "A", "A-", "B+", "B"):
                    lessons["what_worked"].append(f"{agent_id}: {data.get('reasoning', grade)}")
                elif grade in ("D", "D-", "F"):
                    lessons["what_didnt"].append(f"{agent_id}: {data.get('reasoning', grade)}")

        dna = CampaignDNA(
            campaign_id=campaign.id,
            icp_type=biz.icp,
            service_type=biz.service,
            geography=biz.geography,
            entity_type=biz.entity_type,
            industry=biz.industry,
            channel_mix=channel_mix,
            messaging_angles=angles,
            outcomes=outcomes,
            lessons=lessons,
        )

        self._dna_store[campaign.id] = dna
        logger.info(f"Recorded DNA for campaign {campaign.id}: {biz.name}")

        # Persist to database (non-blocking)
        try:
            import asyncio
            from db import save_genome_dna
            dna_dict = {
                "campaign_id": campaign.id,
                "icp_type": dna.icp_type,
                "service_type": dna.service_type,
                "geography": dna.geography,
                "industry": dna.industry,
                "channel_mix": dna.channel_mix,
                "messaging_angles": dna.messaging_angles,
                "outcomes": dna.outcomes,
                "lessons": dna.lessons.__dict__ if hasattr(dna.lessons, '__dict__') else {},
                "created_at": dna.created_at.isoformat() if hasattr(dna.created_at, 'isoformat') else str(dna.created_at),
            }
            asyncio.create_task(save_genome_dna(dna_dict))
        except Exception:
            pass  # Best-effort persistence

        return dna

    async def load_from_db(self):
        """Hydrate in-memory DNA store from database on startup."""
        try:
            from db import load_all_genome_dna
            db_dna = await load_all_genome_dna()
            for entry in db_dna:
                cid = entry.get("campaign_id", "")
                if cid and cid not in self._dna_store:
                    self._dna_store[cid] = CampaignDNA(
                        icp_type=entry.get("icp_type", ""),
                        service_type=entry.get("service_type", ""),
                        geography=entry.get("geography", ""),
                        industry=entry.get("industry", ""),
                        channel_mix=entry.get("channel_mix", {}),
                        messaging_angles=entry.get("messaging_angles", []),
                        outcomes=entry.get("outcomes", {}),
                    )
            logger.info(f"Loaded {len(db_dna)} campaign DNA entries from database")
        except Exception as e:
            logger.debug(f"Failed to load genome from DB: {e}")

    def query_intelligence(
        self,
        icp_type: str = "",
        service_type: str = "",
        geography: str = "",
        industry: str = "",
        min_similarity: float = 0.3,
    ) -> dict[str, Any]:
        """Query aggregated intelligence from similar campaigns."""
        if not self._dna_store:
            return {"matches": 0, "message": "No campaign data yet"}

        # Find similar campaigns
        scored = []
        for dna in self._dna_store.values():
            sim = dna.similarity_score(icp_type, service_type, geography, industry)
            if sim >= min_similarity:
                scored.append((sim, dna))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return {"matches": 0, "message": "No similar campaigns found"}

        # Aggregate outcomes across matches
        agg_outcomes: dict[str, list[float]] = {}
        all_worked: list[str] = []
        all_didnt: list[str] = []
        channel_counts: dict[str, int] = {}

        for _sim, dna in scored:
            for key, val in dna.outcomes.items():
                agg_outcomes.setdefault(key, []).append(val)
            all_worked.extend(dna.lessons.get("what_worked", []))
            all_didnt.extend(dna.lessons.get("what_didnt", []))
            for ch, active in dna.channel_mix.items():
                if active:
                    channel_counts[ch] = channel_counts.get(ch, 0) + 1

        # Calculate averages
        avg_outcomes = {k: round(sum(v) / len(v), 4) for k, v in agg_outcomes.items()}

        # Rank channels by popularity
        total = len(scored)
        channel_ranking = sorted(
            [(ch, count / total) for ch, count in channel_counts.items()],
            key=lambda x: x[1],
            reverse=True,
        )

        return {
            "matches": len(scored),
            "avg_outcomes": avg_outcomes,
            "top_channels": [{"channel": ch, "usage_pct": round(pct * 100, 1)} for ch, pct in channel_ranking],
            "what_worked": all_worked[:10],
            "what_didnt": all_didnt[:10],
            "similar_campaigns": [
                {"campaign_id": dna.campaign_id, "similarity": round(sim, 2),
                 "service": dna.service_type, "icp": dna.icp_type}
                for sim, dna in scored[:5]
            ],
        }

    def get_recommendations(self, campaign: Campaign) -> dict[str, Any]:
        """Generate recommendations for a campaign based on similar historical data."""
        biz = campaign.memory.business
        intel = self.query_intelligence(
            icp_type=biz.icp,
            service_type=biz.service,
            geography=biz.geography,
            industry=biz.industry,
        )

        if intel.get("matches", 0) == 0:
            return {
                "has_data": False,
                "message": "No similar campaigns found yet. Recommendations will improve as more campaigns run.",
                "default_channels": ["outreach", "content", "social"],
                "default_focus": "Start with cold outreach and content marketing as baseline channels.",
            }

        # Build recommendations from data
        recs: list[str] = []

        # Channel recommendations
        top_channels = intel.get("top_channels", [])
        if top_channels:
            top_names = [c["channel"] for c in top_channels[:3]]
            recs.append(f"Focus on: {', '.join(top_names)} (most effective for similar campaigns)")

        # Outcome benchmarks
        avg = intel.get("avg_outcomes", {})
        if "reply_rate" in avg:
            recs.append(f"Target reply rate: {avg['reply_rate']:.1%} (avg for similar ICPs)")
        if "cpa" in avg:
            recs.append(f"Expected CPA: ${avg['cpa']:.2f} (avg for similar service types)")
        if "roas" in avg:
            recs.append(f"Expected ROAS: {avg['roas']:.1f}x")

        # Lessons
        worked = intel.get("what_worked", [])
        if worked:
            recs.append(f"What worked before: {worked[0]}")

        didnt = intel.get("what_didnt", [])
        if didnt:
            recs.append(f"Watch out for: {didnt[0]}")

        return {
            "has_data": True,
            "matches": intel["matches"],
            "recommendations": recs,
            "suggested_channels": [c["channel"] for c in top_channels[:4]],
            "benchmarks": avg,
            "similar_campaigns": intel.get("similar_campaigns", []),
        }

    def update_outcomes(self, campaign_id: str, outcomes: dict[str, float]) -> bool:
        """Update outcomes for an existing campaign DNA entry."""
        dna = self._dna_store.get(campaign_id)
        if not dna:
            return False
        dna.outcomes.update(outcomes)
        logger.info(f"Updated outcomes for campaign {campaign_id}")
        return True

    def add_lesson(self, campaign_id: str, category: str, lesson: str) -> bool:
        """Add a lesson learned to a campaign's DNA."""
        dna = self._dna_store.get(campaign_id)
        if not dna:
            return False
        if category in ("what_worked", "what_didnt"):
            dna.lessons.setdefault(category, []).append(lesson)
            return True
        return False

    def get_all(self) -> list[dict[str, Any]]:
        """Return all campaign DNA entries."""
        return [dna.to_dict() for dna in self._dna_store.values()]

    def get_dna(self, campaign_id: str) -> Optional[dict[str, Any]]:
        """Get DNA for a specific campaign."""
        dna = self._dna_store.get(campaign_id)
        return dna.to_dict() if dna else None


    # ── Adaptive Loop Methods ─────────────────────────────────────────────

    def get_live_intelligence(self, campaign: Campaign) -> dict[str, Any]:
        """Get fresh genome intelligence (not the stale creation-time string).
        Called by adaptation.py on every agent run."""
        biz = campaign.memory.business
        return self.query_intelligence(
            icp_type=biz.icp,
            service_type=biz.service,
            geography=biz.geography,
            industry=biz.industry,
        )

    def record_scoring_outcomes(
        self, campaign: Campaign, scores: dict[str, dict],
    ) -> None:
        """Feed scoring grades + sensing metrics back into campaign DNA.
        Called by the health_check scheduler job to keep genome current."""
        dna = self._dna_store.get(campaign.id)
        if not dna:
            dna = self.record_campaign_dna(campaign)

        # Update outcomes from raw sensing metrics
        raw_metrics = getattr(campaign, '_metrics', {})
        outcome_map = {
            "email_metrics": ["reply_rate", "open_rate", "click_rate", "bounce_rate"],
            "ad_metrics": ["ctr", "cpa", "roas"],
            "site_metrics": ["bounce_rate", "conversion_rate"],
            "social_metrics": ["engagement_rate"],
            "crm_metrics": ["close_rate"],
            "revenue_metrics": ["mrr", "total_revenue"],
            "billing_metrics": ["collection_rate"],
        }
        for source, keys in outcome_map.items():
            source_metrics = raw_metrics.get(source, {})
            for key in keys:
                if key in source_metrics:
                    dna.outcomes[key] = source_metrics[key]

        # Record lessons from agent scores
        for agent_id, data in scores.items():
            grade = data.get("grade", "")
            reasoning = data.get("reasoning", "")
            if not reasoning:
                continue
            lesson = f"{agent_id}: {reasoning}"
            if grade in ("A+", "A", "A-"):
                if lesson not in dna.lessons["what_worked"]:
                    dna.lessons["what_worked"].append(lesson)
                    # Cap at 20 lessons
                    dna.lessons["what_worked"] = dna.lessons["what_worked"][-20:]
            elif grade in ("D", "D-", "F"):
                if lesson not in dna.lessons["what_didnt"]:
                    dna.lessons["what_didnt"].append(lesson)
                    dna.lessons["what_didnt"] = dna.lessons["what_didnt"][-20:]

        logger.info(f"Scoring outcomes recorded for campaign {campaign.id}")


# Singleton
genome = CampaignGenome()
