"""
Supervisor Backend — Sensing Engine
Ingests performance data from webhooks and updates campaign memory.
Triggers agent re-evaluation when thresholds are breached.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Optional

from models import Campaign, PerformanceEvent

logger = logging.getLogger("supervisor.sensing")


class SensingEngine:
    """Ingests performance data and updates campaign memory."""

    def __init__(self):
        self._triggers: list[dict] = []

    async def process_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Route event to appropriate handler and check triggers."""
        handler = {
            "sendgrid": self._process_email_event,
            "meta_ads": self._process_ad_event,
            "google_ads": self._process_ad_event,
            "analytics": self._process_site_event,
            "hubspot": self._process_crm_event,
            "twitter": self._process_social_event,
            "stripe": self._process_payment_event,
        }.get(event.source)

        if handler:
            return await handler(campaign, event)
        logger.warning(f"Unknown event source: {event.source}")
        return None

    async def _process_email_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track email open rates, reply rates, bounce rates per variant."""
        data = event.data
        event_type = data.get("event", "")
        metrics = _get_or_init(campaign, "email_metrics", {
            "sent": 0, "delivered": 0, "opened": 0, "clicked": 0,
            "replied": 0, "bounced": 0, "unsubscribed": 0,
        })

        if event_type == "delivered":
            metrics["delivered"] += 1
        elif event_type == "open":
            metrics["opened"] += 1
        elif event_type == "click":
            metrics["clicked"] += 1
        elif event_type == "bounce":
            metrics["bounced"] += 1
        elif event_type == "reply":
            metrics["replied"] += 1
        elif event_type == "unsubscribe":
            metrics["unsubscribed"] += 1

        # Calculate rates
        if metrics["delivered"] > 0:
            metrics["open_rate"] = round(metrics["opened"] / metrics["delivered"] * 100, 1)
            metrics["click_rate"] = round(metrics["clicked"] / metrics["delivered"] * 100, 1)
            metrics["reply_rate"] = round(metrics["replied"] / metrics["delivered"] * 100, 1)
            metrics["bounce_rate"] = round(metrics["bounced"] / (metrics["delivered"] + metrics["bounced"]) * 100, 1)

        # Trigger: if reply_rate < 2% for 3+ days of data → re-run Outreach
        if metrics.get("delivered", 0) >= 50 and metrics.get("reply_rate", 100) < 2.0:
            return {"trigger": "rerun_agent", "agent_id": "outreach",
                    "reason": f"Reply rate at {metrics['reply_rate']}% after {metrics['delivered']} delivered"}

        return None

    async def _process_ad_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track CPA, CTR, ROAS per campaign/variant."""
        data = event.data
        metrics = _get_or_init(campaign, "ad_metrics", {
            "impressions": 0, "clicks": 0, "conversions": 0,
            "spend": 0.0, "revenue": 0.0,
        })

        metrics["impressions"] += data.get("impressions", 0)
        metrics["clicks"] += data.get("clicks", 0)
        metrics["conversions"] += data.get("conversions", 0)
        metrics["spend"] += data.get("spend", 0.0)
        metrics["revenue"] += data.get("revenue", 0.0)

        if metrics["impressions"] > 0:
            metrics["ctr"] = round(metrics["clicks"] / metrics["impressions"] * 100, 2)
        if metrics["conversions"] > 0:
            metrics["cpa"] = round(metrics["spend"] / metrics["conversions"], 2)
        if metrics["spend"] > 0:
            metrics["roas"] = round(metrics["revenue"] / metrics["spend"], 2)

        # Trigger: if CPA > $200 after 7+ days → PPC agent re-optimizes
        target_cpa = data.get("target_cpa", 200)
        if metrics.get("conversions", 0) >= 5 and metrics.get("cpa", 0) > target_cpa:
            return {"trigger": "rerun_agent", "agent_id": "ppc",
                    "reason": f"CPA at ${metrics['cpa']:.2f} exceeds target ${target_cpa}"}

        return None

    async def _process_site_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track traffic, bounce rate, conversion rate."""
        data = event.data
        metrics = _get_or_init(campaign, "site_metrics", {
            "sessions": 0, "pageviews": 0, "bounces": 0,
            "conversions": 0, "avg_session_duration": 0,
        })

        metrics["sessions"] += data.get("sessions", 0)
        metrics["pageviews"] += data.get("pageviews", 0)
        metrics["bounces"] += data.get("bounces", 0)
        metrics["conversions"] += data.get("conversions", 0)

        if metrics["sessions"] > 0:
            metrics["bounce_rate"] = round(metrics["bounces"] / metrics["sessions"] * 100, 1)
            metrics["conversion_rate"] = round(metrics["conversions"] / metrics["sessions"] * 100, 2)

        # Trigger: bounce_rate > 70% → Content agent reviews page
        if metrics.get("sessions", 0) >= 100 and metrics.get("bounce_rate", 0) > 70:
            return {"trigger": "rerun_agent", "agent_id": "content",
                    "reason": f"Bounce rate at {metrics['bounce_rate']}% across {metrics['sessions']} sessions"}

        return None

    async def _process_crm_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track pipeline value, close rates, deal velocity."""
        data = event.data
        metrics = _get_or_init(campaign, "crm_metrics", {
            "total_deals": 0, "won_deals": 0, "lost_deals": 0,
            "pipeline_value": 0.0, "won_value": 0.0,
        })

        event_type = data.get("event_type", "")
        if event_type == "deal_created":
            metrics["total_deals"] += 1
            metrics["pipeline_value"] += data.get("value", 0)
        elif event_type == "deal_won":
            metrics["won_deals"] += 1
            metrics["won_value"] += data.get("value", 0)
            metrics["pipeline_value"] -= data.get("value", 0)
        elif event_type == "deal_lost":
            metrics["lost_deals"] += 1
            metrics["pipeline_value"] -= data.get("value", 0)

        if metrics["total_deals"] > 0:
            metrics["close_rate"] = round(metrics["won_deals"] / metrics["total_deals"] * 100, 1)

        # Trigger: pipeline drops 20% → Prospector runs additional batch
        prev_pipeline = data.get("previous_pipeline_value", 0)
        if prev_pipeline > 0 and metrics["pipeline_value"] < prev_pipeline * 0.8:
            return {"trigger": "rerun_agent", "agent_id": "prospector",
                    "reason": f"Pipeline dropped from ${prev_pipeline:,.0f} to ${metrics['pipeline_value']:,.0f}"}

        return None

    async def _process_social_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track engagement rates, follower growth."""
        data = event.data
        metrics = _get_or_init(campaign, "social_metrics", {
            "posts": 0, "impressions": 0, "engagements": 0,
            "followers_gained": 0, "dms_received": 0,
        })

        metrics["posts"] += data.get("posts", 0)
        metrics["impressions"] += data.get("impressions", 0)
        metrics["engagements"] += data.get("engagements", 0)
        metrics["followers_gained"] += data.get("followers_gained", 0)
        metrics["dms_received"] += data.get("dms_received", 0)

        if metrics["impressions"] > 0:
            metrics["engagement_rate"] = round(metrics["engagements"] / metrics["impressions"] * 100, 2)

        return None

    async def _process_payment_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track revenue from Stripe payments and billing health."""
        data = event.data
        metrics = _get_or_init(campaign, "revenue_metrics", {
            "total_revenue": 0.0, "mrr": 0.0, "customers": 0,
            "failed_payments": 0, "collection_rate": 100.0,
        })
        billing = _get_or_init(campaign, "billing_metrics", {
            "invoices_sent": 0, "invoices_paid": 0, "invoices_overdue": 0,
            "total_collected": 0.0, "total_outstanding": 0.0,
            "collection_rate": 100.0,
        })

        event_type = data.get("type", "")
        if event_type == "payment_intent.succeeded":
            amount = data.get("amount", 0) / 100
            metrics["total_revenue"] += amount
            metrics["customers"] += 1
            billing["total_collected"] += amount
        elif event_type == "invoice.paid":
            billing["invoices_paid"] += 1
        elif event_type == "invoice.sent":
            billing["invoices_sent"] += 1
        elif event_type == "invoice.overdue" or event_type == "invoice.payment_failed":
            billing["invoices_overdue"] += 1
            metrics["failed_payments"] += 1
        elif event_type == "customer.subscription.created":
            mrr_amount = data.get("amount", 0) / 100
            metrics["mrr"] += mrr_amount

        # Update collection rate
        if billing["invoices_sent"] > 0:
            billing["collection_rate"] = round(
                billing["invoices_paid"] / billing["invoices_sent"] * 100, 1)
            metrics["collection_rate"] = billing["collection_rate"]

        # Trigger: collection rate drops below 80% → billing agent re-runs dunning
        if billing["invoices_sent"] >= 5 and billing["collection_rate"] < 80:
            return {"trigger": "rerun_agent", "agent_id": "billing",
                    "reason": f"Collection rate at {billing['collection_rate']}% — {billing['invoices_overdue']} overdue invoices"}

        return None


def _get_or_init(campaign: Campaign, key: str, defaults: dict) -> dict:
    """Get or initialize a metrics dict in campaign memory brand_context."""
    # Store metrics as a sub-dict in campaign memory
    if not hasattr(campaign, '_metrics'):
        campaign._metrics = {}  # type: ignore[attr-defined]
    if key not in campaign._metrics:  # type: ignore[attr-defined]
        campaign._metrics[key] = defaults.copy()  # type: ignore[attr-defined]
    return campaign._metrics[key]  # type: ignore[attr-defined]


sensing = SensingEngine()
