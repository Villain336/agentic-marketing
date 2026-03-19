"""
Omni OS Backend — Sensing Engine
Ingests performance data from webhooks and updates campaign memory.
Triggers agent re-evaluation when thresholds are breached.
Persists metrics to Supabase so they survive restarts.
Tracks variants/experiments for A/B testing.
"""
from __future__ import annotations
import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional

from models import Campaign, PerformanceEvent

logger = logging.getLogger("supervisor.sensing")

# --- Configurable thresholds (can be overridden per-campaign via brand_context) ---
DEFAULT_THRESHOLDS = {
    "email_reply_rate_min": 2.0,           # % — below this triggers outreach rerun
    "email_min_delivered": 50,             # min sample before triggering
    "ad_target_cpa": 200.0,               # $ — above this triggers ppc rerun
    "ad_min_conversions": 5,              # min sample before triggering
    "ad_roas_min": 1.0,                   # below this triggers ppc rerun
    "site_bounce_rate_max": 70.0,         # % — above this triggers content rerun
    "site_min_sessions": 100,             # min sample before triggering
    "site_conversion_rate_min": 1.0,      # % — below this triggers sitelaunch rerun
    "crm_pipeline_drop_pct": 20.0,        # % drop triggers prospector rerun
    "crm_close_rate_min": 10.0,           # % — below this triggers sales rerun
    "crm_min_deals": 10,                  # min sample before triggering
    "social_engagement_rate_min": 1.0,    # % — below this triggers social rerun
    "social_min_impressions": 1000,       # min sample before triggering
    "social_follower_growth_min": 0.5,    # % weekly growth — below triggers rerun
    "revenue_collection_rate_min": 80.0,  # % — below this triggers billing rerun
    "revenue_min_invoices": 5,            # min sample before triggering
    "revenue_mrr_drop_pct": 10.0,         # % MRR drop triggers retention rerun
    "revenue_churn_rate_max": 5.0,        # % monthly churn triggers retention rerun
}


def _get_thresholds(campaign: Campaign) -> dict:
    """Get thresholds, allowing per-campaign overrides from brand_context."""
    thresholds = DEFAULT_THRESHOLDS.copy()
    if hasattr(campaign, "brand_context") and isinstance(campaign.brand_context, dict):
        overrides = campaign.brand_context.get("sensing_thresholds", {})
        if isinstance(overrides, dict):
            thresholds.update(overrides)
    return thresholds


class SensingEngine:
    """Ingests performance data and updates campaign memory.

    Metrics are accumulated in campaign._metrics (in-memory) and persisted
    to Supabase on every event so they survive process restarts. On first
    access for a campaign, metrics are loaded from Supabase if available.
    """

    def __init__(self):
        self._triggers: list[dict] = []
        self._trigger_history: dict[str, list[dict]] = {}  # campaign_id -> trigger log
        self._pipeline_history: dict[str, float] = {}  # campaign_id -> last known pipeline value

    async def process_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Route event to appropriate handler and check triggers."""
        handler = {
            "sendgrid": self._process_email_event,
            "meta_ads": self._process_ad_event,
            "google_ads": self._process_ad_event,
            "analytics": self._process_site_event,
            "hubspot": self._process_crm_event,
            "twitter": self._process_social_event,
            "linkedin": self._process_social_event,
            "instagram": self._process_social_event,
            "tiktok": self._process_social_event,
            "stripe": self._process_payment_event,
        }.get(event.source)

        if handler:
            result = await handler(campaign, event)
            # Persist metrics after every event
            await self._persist_metrics(campaign)
            # Log trigger if one was produced
            if result and result.get("trigger"):
                result["timestamp"] = datetime.now(timezone.utc).isoformat()
                result["event_source"] = event.source
                cid = str(getattr(campaign, "id", "unknown"))
                self._trigger_history.setdefault(cid, []).append(result)
                self._triggers.append(result)
            return result
        logger.warning(f"Unknown event source: {event.source}")
        return None

    async def load_metrics_from_db(self, campaign: Campaign) -> None:
        """Load persisted metrics from Supabase into campaign._metrics on startup."""
        try:
            from config import settings
            if not settings.supabase_url or not settings.supabase_key:
                return
            import httpx
            url = f"{settings.supabase_url}/rest/v1/campaign_metrics"
            headers = {
                "apikey": settings.supabase_key,
                "Authorization": f"Bearer {settings.supabase_key}",
            }
            cid = str(getattr(campaign, "id", ""))
            if not cid:
                return
            params = {"campaign_id": f"eq.{cid}", "select": "metric_key,metric_data"}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    rows = resp.json()
                    if rows:
                        if not hasattr(campaign, "_metrics"):
                            campaign._metrics = {}  # type: ignore[attr-defined]
                        for row in rows:
                            campaign._metrics[row["metric_key"]] = row["metric_data"]  # type: ignore[attr-defined]
                        logger.info(f"Loaded {len(rows)} metric groups for campaign {cid}")
        except Exception as e:
            logger.error(f"Failed to load metrics from DB for campaign: {e}")

    async def _persist_metrics(self, campaign: Campaign) -> None:
        """Persist current metrics to Supabase (upsert per metric key)."""
        try:
            from config import settings
            if not settings.supabase_url or not settings.supabase_key:
                return
            if not hasattr(campaign, "_metrics"):
                return
            import httpx
            url = f"{settings.supabase_url}/rest/v1/campaign_metrics"
            headers = {
                "apikey": settings.supabase_key,
                "Authorization": f"Bearer {settings.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            }
            cid = str(getattr(campaign, "id", ""))
            if not cid:
                return
            async with httpx.AsyncClient(timeout=10) as client:
                for key, data in campaign._metrics.items():  # type: ignore[attr-defined]
                    payload = {
                        "campaign_id": cid,
                        "metric_key": key,
                        "metric_data": data,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code not in (200, 201):
                        logger.error(f"Failed to persist {key} for campaign {cid}: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Metrics persistence failed for campaign: {e}")

    def get_trigger_history(self, campaign_id: str) -> list[dict]:
        """Return all triggers fired for a campaign — useful for debugging."""
        return self._trigger_history.get(campaign_id, [])

    def get_all_metrics(self, campaign: Campaign) -> dict:
        """Return all accumulated metrics for a campaign."""
        if hasattr(campaign, "_metrics"):
            return dict(campaign._metrics)  # type: ignore[attr-defined]
        return {}

    # ---- Email ----

    async def _process_email_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track email open rates, reply rates, bounce rates per variant."""
        data = event.data
        event_type = data.get("event", "")
        variant = data.get("variant", "default")

        metrics = _get_or_init(campaign, "email_metrics", {
            "sent": 0, "delivered": 0, "opened": 0, "clicked": 0,
            "replied": 0, "bounced": 0, "unsubscribed": 0,
            "variants": {},
        })

        # Initialize variant tracking
        if variant not in metrics["variants"]:
            metrics["variants"][variant] = {
                "sent": 0, "delivered": 0, "opened": 0, "clicked": 0,
                "replied": 0, "bounced": 0,
            }
        v = metrics["variants"][variant]

        if event_type == "delivered":
            metrics["delivered"] += 1
            v["delivered"] += 1
        elif event_type == "open":
            metrics["opened"] += 1
            v["opened"] += 1
        elif event_type == "click":
            metrics["clicked"] += 1
            v["clicked"] += 1
        elif event_type == "bounce":
            metrics["bounced"] += 1
            v["bounced"] += 1
        elif event_type == "reply":
            metrics["replied"] += 1
            v["replied"] += 1
        elif event_type == "unsubscribe":
            metrics["unsubscribed"] += 1
        elif event_type == "sent":
            metrics["sent"] += 1
            v["sent"] += 1

        # Calculate aggregate rates
        if metrics["delivered"] > 0:
            metrics["open_rate"] = round(metrics["opened"] / metrics["delivered"] * 100, 1)
            metrics["click_rate"] = round(metrics["clicked"] / metrics["delivered"] * 100, 1)
            metrics["reply_rate"] = round(metrics["replied"] / metrics["delivered"] * 100, 1)
            total_attempted = metrics["delivered"] + metrics["bounced"]
            metrics["bounce_rate"] = round(metrics["bounced"] / total_attempted * 100, 1) if total_attempted > 0 else 0

        # Calculate per-variant rates
        for vname, vdata in metrics["variants"].items():
            if vdata["delivered"] > 0:
                vdata["open_rate"] = round(vdata["opened"] / vdata["delivered"] * 100, 1)
                vdata["click_rate"] = round(vdata["clicked"] / vdata["delivered"] * 100, 1)
                vdata["reply_rate"] = round(vdata["replied"] / vdata["delivered"] * 100, 1)

        thresholds = _get_thresholds(campaign)

        # Trigger: reply_rate below threshold with sufficient sample
        if (metrics["delivered"] >= thresholds["email_min_delivered"]
                and metrics.get("reply_rate", 100) < thresholds["email_reply_rate_min"]):
            return {"trigger": "rerun_agent", "agent_id": "outreach",
                    "reason": f"Reply rate at {metrics['reply_rate']}% after {metrics['delivered']} delivered",
                    "metrics_snapshot": {"reply_rate": metrics["reply_rate"], "open_rate": metrics.get("open_rate", 0)}}

        # Trigger: open rate below 10% means subject lines need work
        if metrics["delivered"] >= thresholds["email_min_delivered"] and metrics.get("open_rate", 100) < 10.0:
            return {"trigger": "rerun_agent", "agent_id": "outreach",
                    "reason": f"Open rate at {metrics['open_rate']}% — subject lines ineffective",
                    "metrics_snapshot": {"open_rate": metrics["open_rate"], "delivered": metrics["delivered"]}}

        return None

    # ---- Ads (Meta, Google) ----

    async def _process_ad_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track CPA, CTR, ROAS per campaign/variant."""
        data = event.data
        variant = data.get("variant", data.get("ad_group", "default"))

        metrics = _get_or_init(campaign, "ad_metrics", {
            "impressions": 0, "clicks": 0, "conversions": 0,
            "spend": 0.0, "revenue": 0.0, "variants": {},
        })

        # Track by variant/ad group
        if variant not in metrics["variants"]:
            metrics["variants"][variant] = {
                "impressions": 0, "clicks": 0, "conversions": 0,
                "spend": 0.0, "revenue": 0.0,
            }
        v = metrics["variants"][variant]

        for key in ("impressions", "clicks", "conversions"):
            val = data.get(key, 0)
            metrics[key] += val
            v[key] += val
        for key in ("spend", "revenue"):
            val = data.get(key, 0.0)
            metrics[key] += val
            v[key] += val

        # Calculate aggregate rates
        if metrics["impressions"] > 0:
            metrics["ctr"] = round(metrics["clicks"] / metrics["impressions"] * 100, 2)
        if metrics["conversions"] > 0:
            metrics["cpa"] = round(metrics["spend"] / metrics["conversions"], 2)
        if metrics["spend"] > 0:
            metrics["roas"] = round(metrics["revenue"] / metrics["spend"], 2)

        # Per-variant rates
        for vname, vdata in metrics["variants"].items():
            if vdata["impressions"] > 0:
                vdata["ctr"] = round(vdata["clicks"] / vdata["impressions"] * 100, 2)
            if vdata["conversions"] > 0:
                vdata["cpa"] = round(vdata["spend"] / vdata["conversions"], 2)
            if vdata["spend"] > 0:
                vdata["roas"] = round(vdata["revenue"] / vdata["spend"], 2)

        thresholds = _get_thresholds(campaign)
        target_cpa = data.get("target_cpa", thresholds["ad_target_cpa"])

        # Trigger: CPA exceeds target
        if metrics.get("conversions", 0) >= thresholds["ad_min_conversions"] and metrics.get("cpa", 0) > target_cpa:
            return {"trigger": "rerun_agent", "agent_id": "ppc",
                    "reason": f"CPA at ${metrics['cpa']:.2f} exceeds target ${target_cpa:.2f}",
                    "metrics_snapshot": {"cpa": metrics["cpa"], "roas": metrics.get("roas", 0), "conversions": metrics["conversions"]}}

        # Trigger: ROAS below minimum
        if (metrics.get("spend", 0) >= 100
                and metrics.get("roas", 999) < thresholds["ad_roas_min"]):
            return {"trigger": "rerun_agent", "agent_id": "ppc",
                    "reason": f"ROAS at {metrics['roas']:.2f}x on ${metrics['spend']:.2f} spend",
                    "metrics_snapshot": {"roas": metrics["roas"], "spend": metrics["spend"]}}

        return None

    # ---- Site Analytics ----

    async def _process_site_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track traffic, bounce rate, conversion rate with session duration."""
        data = event.data
        metrics = _get_or_init(campaign, "site_metrics", {
            "sessions": 0, "pageviews": 0, "bounces": 0,
            "conversions": 0, "total_session_duration": 0, "avg_session_duration": 0,
            "pages": {},  # per-page metrics
        })

        new_sessions = data.get("sessions", 0)
        metrics["sessions"] += new_sessions
        metrics["pageviews"] += data.get("pageviews", 0)
        metrics["bounces"] += data.get("bounces", 0)
        metrics["conversions"] += data.get("conversions", 0)
        metrics["total_session_duration"] += data.get("session_duration", 0) * new_sessions if new_sessions > 0 else 0

        # Per-page tracking
        page = data.get("page", "")
        if page:
            if page not in metrics["pages"]:
                metrics["pages"][page] = {"sessions": 0, "bounces": 0, "conversions": 0}
            pg = metrics["pages"][page]
            pg["sessions"] += new_sessions
            pg["bounces"] += data.get("bounces", 0)
            pg["conversions"] += data.get("conversions", 0)

        if metrics["sessions"] > 0:
            metrics["bounce_rate"] = round(metrics["bounces"] / metrics["sessions"] * 100, 1)
            metrics["conversion_rate"] = round(metrics["conversions"] / metrics["sessions"] * 100, 2)
            metrics["avg_session_duration"] = round(metrics["total_session_duration"] / metrics["sessions"], 1)

        thresholds = _get_thresholds(campaign)

        # Trigger: high bounce rate
        if (metrics["sessions"] >= thresholds["site_min_sessions"]
                and metrics.get("bounce_rate", 0) > thresholds["site_bounce_rate_max"]):
            # Identify worst page
            worst_page = ""
            worst_bounce = 0
            for pg_name, pg_data in metrics.get("pages", {}).items():
                if pg_data["sessions"] > 10:
                    pg_bounce = pg_data["bounces"] / pg_data["sessions"] * 100
                    if pg_bounce > worst_bounce:
                        worst_bounce = pg_bounce
                        worst_page = pg_name
            return {"trigger": "rerun_agent", "agent_id": "content",
                    "reason": f"Bounce rate at {metrics['bounce_rate']}% across {metrics['sessions']} sessions"
                              + (f" (worst: {worst_page} at {worst_bounce:.0f}%)" if worst_page else ""),
                    "metrics_snapshot": {"bounce_rate": metrics["bounce_rate"], "sessions": metrics["sessions"]}}

        # Trigger: low conversion rate
        if (metrics["sessions"] >= thresholds["site_min_sessions"]
                and metrics.get("conversion_rate", 100) < thresholds["site_conversion_rate_min"]):
            return {"trigger": "rerun_agent", "agent_id": "sitelaunch",
                    "reason": f"Conversion rate at {metrics['conversion_rate']}% across {metrics['sessions']} sessions",
                    "metrics_snapshot": {"conversion_rate": metrics["conversion_rate"], "bounce_rate": metrics.get("bounce_rate", 0)}}

        return None

    # ---- CRM / Pipeline ----

    async def _process_crm_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track pipeline value, close rates, deal velocity. Tracks pipeline history internally."""
        data = event.data
        metrics = _get_or_init(campaign, "crm_metrics", {
            "total_deals": 0, "won_deals": 0, "lost_deals": 0,
            "pipeline_value": 0.0, "won_value": 0.0,
            "deal_values": [],  # track individual deal values for velocity
            "stages": {},  # deals per stage
        })

        cid = str(getattr(campaign, "id", "unknown"))

        # Record previous pipeline value internally before mutation
        prev_pipeline = self._pipeline_history.get(cid, metrics["pipeline_value"])

        event_type = data.get("event_type", "")
        deal_value = data.get("value", 0)
        stage = data.get("stage", "")

        if event_type == "deal_created":
            metrics["total_deals"] += 1
            metrics["pipeline_value"] += deal_value
            metrics["deal_values"].append({"value": deal_value, "ts": datetime.now(timezone.utc).isoformat()})
            if stage:
                metrics["stages"][stage] = metrics["stages"].get(stage, 0) + 1
        elif event_type == "deal_won":
            metrics["won_deals"] += 1
            metrics["won_value"] += deal_value
            metrics["pipeline_value"] = max(0, metrics["pipeline_value"] - deal_value)
        elif event_type == "deal_lost":
            metrics["lost_deals"] += 1
            metrics["pipeline_value"] = max(0, metrics["pipeline_value"] - deal_value)
        elif event_type == "deal_stage_changed":
            old_stage = data.get("old_stage", "")
            new_stage = data.get("new_stage", "")
            if old_stage:
                metrics["stages"][old_stage] = max(0, metrics["stages"].get(old_stage, 1) - 1)
            if new_stage:
                metrics["stages"][new_stage] = metrics["stages"].get(new_stage, 0) + 1

        # Update pipeline history after mutation
        self._pipeline_history[cid] = metrics["pipeline_value"]

        if metrics["total_deals"] > 0:
            metrics["close_rate"] = round(metrics["won_deals"] / metrics["total_deals"] * 100, 1)
            if metrics["won_deals"] > 0:
                metrics["avg_deal_value"] = round(metrics["won_value"] / metrics["won_deals"], 2)

        thresholds = _get_thresholds(campaign)

        # Trigger: pipeline drops by configured percentage
        drop_threshold = thresholds["crm_pipeline_drop_pct"] / 100
        if prev_pipeline > 0 and metrics["pipeline_value"] < prev_pipeline * (1 - drop_threshold):
            return {"trigger": "rerun_agent", "agent_id": "prospector",
                    "reason": f"Pipeline dropped {((prev_pipeline - metrics['pipeline_value']) / prev_pipeline * 100):.0f}% "
                              f"from ${prev_pipeline:,.0f} to ${metrics['pipeline_value']:,.0f}",
                    "metrics_snapshot": {"pipeline_value": metrics["pipeline_value"], "prev_pipeline": prev_pipeline}}

        # Trigger: close rate too low with sufficient deals
        if (metrics["total_deals"] >= thresholds["crm_min_deals"]
                and metrics.get("close_rate", 100) < thresholds["crm_close_rate_min"]):
            return {"trigger": "rerun_agent", "agent_id": "sales",
                    "reason": f"Close rate at {metrics['close_rate']}% across {metrics['total_deals']} deals",
                    "metrics_snapshot": {"close_rate": metrics["close_rate"], "total_deals": metrics["total_deals"]}}

        return None

    # ---- Social Media ----

    async def _process_social_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track engagement rates, follower growth, sentiment. Triggers on low engagement."""
        data = event.data
        platform = event.source  # twitter, linkedin, instagram, tiktok
        metrics = _get_or_init(campaign, "social_metrics", {
            "posts": 0, "impressions": 0, "engagements": 0,
            "followers_gained": 0, "followers_lost": 0, "dms_received": 0,
            "shares": 0, "comments": 0, "saves": 0,
            "platforms": {},  # per-platform breakdown
            "weekly_snapshots": [],  # for growth trending
        })

        # Per-platform tracking
        if platform not in metrics["platforms"]:
            metrics["platforms"][platform] = {
                "posts": 0, "impressions": 0, "engagements": 0,
                "followers_gained": 0, "followers_lost": 0,
            }
        p = metrics["platforms"][platform]

        for key in ("posts", "impressions", "engagements", "followers_gained", "dms_received", "shares", "comments", "saves"):
            val = data.get(key, 0)
            if key in metrics:
                metrics[key] += val
            if key in p:
                p[key] += val

        metrics["followers_lost"] += data.get("followers_lost", 0)
        p["followers_lost"] = p.get("followers_lost", 0) + data.get("followers_lost", 0)

        # Calculate engagement rate
        if metrics["impressions"] > 0:
            metrics["engagement_rate"] = round(metrics["engagements"] / metrics["impressions"] * 100, 2)

        # Per-platform engagement
        for pname, pdata in metrics["platforms"].items():
            if pdata["impressions"] > 0:
                pdata["engagement_rate"] = round(pdata["engagements"] / pdata["impressions"] * 100, 2)

        # Net follower growth
        metrics["net_followers"] = metrics["followers_gained"] - metrics["followers_lost"]

        thresholds = _get_thresholds(campaign)

        # Trigger: engagement rate below threshold with sufficient impressions
        if (metrics["impressions"] >= thresholds["social_min_impressions"]
                and metrics.get("engagement_rate", 100) < thresholds["social_engagement_rate_min"]):
            # Find worst-performing platform
            worst_platform = ""
            worst_rate = 100
            for pname, pdata in metrics["platforms"].items():
                rate = pdata.get("engagement_rate", 100)
                if pdata.get("impressions", 0) >= 100 and rate < worst_rate:
                    worst_rate = rate
                    worst_platform = pname
            return {"trigger": "rerun_agent", "agent_id": "social",
                    "reason": f"Engagement rate at {metrics['engagement_rate']}% across {metrics['impressions']} impressions"
                              + (f" (worst: {worst_platform} at {worst_rate:.2f}%)" if worst_platform else ""),
                    "metrics_snapshot": {"engagement_rate": metrics["engagement_rate"],
                                         "impressions": metrics["impressions"],
                                         "net_followers": metrics["net_followers"]}}

        # Trigger: losing followers (net negative)
        if metrics["followers_lost"] > 0 and metrics["net_followers"] < 0:
            return {"trigger": "rerun_agent", "agent_id": "social",
                    "reason": f"Net follower loss: {metrics['net_followers']} "
                              f"(gained {metrics['followers_gained']}, lost {metrics['followers_lost']})",
                    "metrics_snapshot": {"net_followers": metrics["net_followers"],
                                         "followers_gained": metrics["followers_gained"],
                                         "followers_lost": metrics["followers_lost"]}}

        return None

    # ---- Payments / Revenue ----

    async def _process_payment_event(self, campaign: Campaign, event: PerformanceEvent) -> Optional[dict]:
        """Track revenue, MRR (including churn), billing health, and customer lifecycle."""
        data = event.data
        metrics = _get_or_init(campaign, "revenue_metrics", {
            "total_revenue": 0.0, "mrr": 0.0, "customers": 0,
            "failed_payments": 0, "collection_rate": 100.0,
            "churned_customers": 0, "churned_mrr": 0.0,
            "upgraded_mrr": 0.0, "downgraded_mrr": 0.0,
            "net_new_mrr": 0.0,  # new + upgrades - downgrades - churn
            "active_subscriptions": 0,
            "mrr_history": [],  # snapshots for trending
        })
        billing = _get_or_init(campaign, "billing_metrics", {
            "invoices_sent": 0, "invoices_paid": 0, "invoices_overdue": 0,
            "total_collected": 0.0, "total_outstanding": 0.0,
            "collection_rate": 100.0,
            "refunds": 0, "refund_amount": 0.0,
        })

        event_type = data.get("type", "")
        prev_mrr = metrics["mrr"]

        if event_type == "payment_intent.succeeded":
            amount = data.get("amount", 0) / 100
            metrics["total_revenue"] += amount
            metrics["customers"] += 1
            billing["total_collected"] += amount
            billing["total_outstanding"] = max(0, billing["total_outstanding"] - amount)

        elif event_type == "invoice.paid":
            billing["invoices_paid"] += 1
            amount = data.get("amount", 0) / 100
            billing["total_collected"] += amount
            billing["total_outstanding"] = max(0, billing["total_outstanding"] - amount)

        elif event_type == "invoice.sent" or event_type == "invoice.created":
            billing["invoices_sent"] += 1
            amount = data.get("amount", 0) / 100
            billing["total_outstanding"] += amount

        elif event_type in ("invoice.overdue", "invoice.payment_failed"):
            billing["invoices_overdue"] += 1
            metrics["failed_payments"] += 1

        elif event_type == "customer.subscription.created":
            mrr_amount = data.get("amount", 0) / 100
            metrics["mrr"] += mrr_amount
            metrics["net_new_mrr"] += mrr_amount
            metrics["active_subscriptions"] += 1

        elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
            # MRR churn — subtract the subscription amount
            mrr_amount = data.get("amount", 0) / 100
            metrics["mrr"] = max(0, metrics["mrr"] - mrr_amount)
            metrics["churned_customers"] += 1
            metrics["churned_mrr"] += mrr_amount
            metrics["active_subscriptions"] = max(0, metrics["active_subscriptions"] - 1)

        elif event_type == "customer.subscription.updated":
            # Handle upgrades and downgrades
            old_amount = data.get("previous_amount", 0) / 100
            new_amount = data.get("amount", 0) / 100
            delta = new_amount - old_amount
            if delta > 0:
                metrics["upgraded_mrr"] += delta
                metrics["mrr"] += delta
            elif delta < 0:
                metrics["downgraded_mrr"] += abs(delta)
                metrics["mrr"] = max(0, metrics["mrr"] + delta)  # delta is negative

        elif event_type == "charge.refunded":
            refund_amount = data.get("amount", 0) / 100
            billing["refunds"] += 1
            billing["refund_amount"] += refund_amount
            metrics["total_revenue"] -= refund_amount

        # Update collection rate
        if billing["invoices_sent"] > 0:
            billing["collection_rate"] = round(
                billing["invoices_paid"] / billing["invoices_sent"] * 100, 1)
            metrics["collection_rate"] = billing["collection_rate"]

        # Calculate churn rate
        total_ever = metrics["active_subscriptions"] + metrics["churned_customers"]
        if total_ever > 0:
            metrics["churn_rate"] = round(metrics["churned_customers"] / total_ever * 100, 1)

        # Snapshot MRR if it changed
        if metrics["mrr"] != prev_mrr:
            metrics["mrr_history"].append({
                "mrr": metrics["mrr"],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            # Keep last 90 snapshots
            if len(metrics["mrr_history"]) > 90:
                metrics["mrr_history"] = metrics["mrr_history"][-90:]

        thresholds = _get_thresholds(campaign)

        # Trigger: collection rate drops below threshold
        if (billing["invoices_sent"] >= thresholds["revenue_min_invoices"]
                and billing["collection_rate"] < thresholds["revenue_collection_rate_min"]):
            return {"trigger": "rerun_agent", "agent_id": "billing",
                    "reason": f"Collection rate at {billing['collection_rate']}% — "
                              f"{billing['invoices_overdue']} overdue invoices, "
                              f"${billing['total_outstanding']:,.2f} outstanding",
                    "metrics_snapshot": {"collection_rate": billing["collection_rate"],
                                         "invoices_overdue": billing["invoices_overdue"],
                                         "total_outstanding": billing["total_outstanding"]}}

        # Trigger: MRR dropped by configured percentage
        if prev_mrr > 0:
            mrr_drop_pct = (prev_mrr - metrics["mrr"]) / prev_mrr * 100
            if mrr_drop_pct >= thresholds["revenue_mrr_drop_pct"]:
                return {"trigger": "rerun_agent", "agent_id": "retention",
                        "reason": f"MRR dropped {mrr_drop_pct:.1f}% from ${prev_mrr:,.2f} to ${metrics['mrr']:,.2f} "
                                  f"({metrics['churned_customers']} churned customers)",
                        "metrics_snapshot": {"mrr": metrics["mrr"], "prev_mrr": prev_mrr,
                                             "churned_mrr": metrics["churned_mrr"]}}

        # Trigger: churn rate exceeds maximum
        if (total_ever >= 10
                and metrics.get("churn_rate", 0) > thresholds["revenue_churn_rate_max"]):
            return {"trigger": "rerun_agent", "agent_id": "retention",
                    "reason": f"Monthly churn rate at {metrics['churn_rate']}% "
                              f"({metrics['churned_customers']} of {total_ever} customers)",
                    "metrics_snapshot": {"churn_rate": metrics["churn_rate"],
                                         "churned_mrr": metrics["churned_mrr"],
                                         "active_subscriptions": metrics["active_subscriptions"]}}

        return None


def _get_or_init(campaign: Campaign, key: str, defaults: dict) -> dict:
    """Get or initialize a metrics dict in campaign._metrics."""
    if not hasattr(campaign, '_metrics'):
        campaign._metrics = {}  # type: ignore[attr-defined]
    if key not in campaign._metrics:  # type: ignore[attr-defined]
        campaign._metrics[key] = defaults.copy()  # type: ignore[attr-defined]
    return campaign._metrics[key]  # type: ignore[attr-defined]


sensing = SensingEngine()
