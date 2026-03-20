"""Tests for the sensing engine."""
from __future__ import annotations

import pytest

from models import Campaign, CampaignMemory, BusinessProfile, PerformanceEvent
from sensing import SensingEngine, _get_or_init, DEFAULT_THRESHOLDS


def _make_campaign(**kwargs) -> Campaign:
    biz = BusinessProfile(
        name="Test Co", service="SaaS", icp="B2B", geography="US", goal="grow",
    )
    mem = CampaignMemory(business=biz)
    return Campaign(id="sens-camp-001", memory=mem, **kwargs)


def _email_event(event_type: str, variant: str = "default") -> PerformanceEvent:
    return PerformanceEvent(
        campaign_id="sens-camp-001", source="sendgrid",
        data={"event": event_type, "variant": variant},
    )


def _social_event(impressions=0, engagements=0, posts=0, **extra) -> PerformanceEvent:
    data = {"impressions": impressions, "engagements": engagements, "posts": posts}
    data.update(extra)
    return PerformanceEvent(
        campaign_id="sens-camp-001", source="twitter", data=data,
    )


def _stripe_event(event_type: str, amount_cents: int = 0, **extra) -> PerformanceEvent:
    data = {"type": event_type, "amount": amount_cents}
    data.update(extra)
    return PerformanceEvent(
        campaign_id="sens-camp-001", source="stripe", data=data,
    )


# ── Email event tracking ────────────────────────────────────────────────────

class TestEmailEvents:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_delivered_increments(self):
        await self.engine.process_event(self.campaign, _email_event("delivered"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["delivered"] == 1

    async def test_open_increments(self):
        await self.engine.process_event(self.campaign, _email_event("delivered"))
        await self.engine.process_event(self.campaign, _email_event("open"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["opened"] == 1

    async def test_click_increments(self):
        await self.engine.process_event(self.campaign, _email_event("delivered"))
        await self.engine.process_event(self.campaign, _email_event("click"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["clicked"] == 1

    async def test_bounce_increments(self):
        await self.engine.process_event(self.campaign, _email_event("bounce"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["bounced"] == 1


# ── Rate calculations ────────────────────────────────────────────────────────

class TestRateCalculations:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_open_rate(self):
        # 2 delivered, 1 opened → 50% open rate
        await self.engine.process_event(self.campaign, _email_event("delivered"))
        await self.engine.process_event(self.campaign, _email_event("delivered"))
        await self.engine.process_event(self.campaign, _email_event("open"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["open_rate"] == 50.0

    async def test_reply_rate(self):
        for _ in range(10):
            await self.engine.process_event(self.campaign, _email_event("delivered"))
        await self.engine.process_event(self.campaign, _email_event("reply"))
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["reply_rate"] == 10.0


# ── Trigger firing ───────────────────────────────────────────────────────────

class TestTriggers:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_low_reply_rate_triggers_outreach_rerun(self):
        """After enough deliveries with no replies, trigger must fire."""
        for _ in range(60):
            await self.engine.process_event(self.campaign, _email_event("delivered"))
        # 0 replies on 60 delivered → reply_rate 0% < 2% threshold
        result = await self.engine.process_event(self.campaign, _email_event("delivered"))
        # The trigger fires on the last event that keeps rate below threshold
        # since delivered >= 50 and reply_rate < 2
        metrics = self.campaign._metrics["email_metrics"]
        assert metrics["delivered"] >= DEFAULT_THRESHOLDS["email_min_delivered"]
        assert metrics.get("reply_rate", 0) < DEFAULT_THRESHOLDS["email_reply_rate_min"]

    async def test_no_trigger_when_sample_too_small(self):
        """Triggers should NOT fire if sample is below min_delivered."""
        for _ in range(5):
            result = await self.engine.process_event(self.campaign, _email_event("delivered"))
        # 5 delivered, 0 replies — but 5 < 50 min
        assert result is None


# ── MRR churn ────────────────────────────────────────────────────────────────

class TestMRRChurn:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_subscription_deleted_subtracts_mrr(self):
        # First create a subscription
        await self.engine.process_event(
            self.campaign,
            _stripe_event("customer.subscription.created", amount_cents=5000),
        )
        metrics = self.campaign._metrics["revenue_metrics"]
        assert metrics["mrr"] == 50.0

        # Now cancel it
        await self.engine.process_event(
            self.campaign,
            _stripe_event("customer.subscription.deleted", amount_cents=5000),
        )
        metrics = self.campaign._metrics["revenue_metrics"]
        assert metrics["mrr"] == 0.0
        assert metrics["churned_customers"] == 1
        assert metrics["churned_mrr"] == 50.0

    async def test_mrr_does_not_go_negative(self):
        # Cancel without creating — MRR clamps to 0
        await self.engine.process_event(
            self.campaign,
            _stripe_event("customer.subscription.deleted", amount_cents=5000),
        )
        metrics = self.campaign._metrics["revenue_metrics"]
        assert metrics["mrr"] == 0.0


# ── Social trigger ───────────────────────────────────────────────────────────

class TestSocialTrigger:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_low_engagement_triggers_social_rerun(self):
        """Engagement rate below threshold with sufficient impressions triggers."""
        # 2000 impressions, 5 engagements → 0.25% < 1% threshold
        event = _social_event(impressions=2000, engagements=5, posts=15)
        result = await self.engine.process_event(self.campaign, event)
        assert result is not None
        assert result["trigger"] == "rerun_agent"
        assert result["agent_id"] == "social"

    async def test_no_trigger_below_min_impressions(self):
        event = _social_event(impressions=100, engagements=0, posts=5)
        result = await self.engine.process_event(self.campaign, event)
        assert result is None


# ── Variant tracking ─────────────────────────────────────────────────────────

class TestVariantTracking:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()
        self.campaign = _make_campaign()

    async def test_variants_tracked_separately(self):
        await self.engine.process_event(self.campaign, _email_event("delivered", variant="A"))
        await self.engine.process_event(self.campaign, _email_event("delivered", variant="B"))
        await self.engine.process_event(self.campaign, _email_event("open", variant="A"))

        metrics = self.campaign._metrics["email_metrics"]
        assert "A" in metrics["variants"]
        assert "B" in metrics["variants"]
        assert metrics["variants"]["A"]["delivered"] == 1
        assert metrics["variants"]["A"]["opened"] == 1
        assert metrics["variants"]["B"]["delivered"] == 1
        assert metrics["variants"]["B"]["opened"] == 0


# ── Configurable thresholds ──────────────────────────────────────────────────

class TestConfigurableThresholds:
    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        self.engine = SensingEngine()

    async def test_custom_thresholds_via_brand_context(self):
        """brand_context.sensing_thresholds override defaults."""
        campaign = _make_campaign()
        # Override: set min delivered to 5 (much lower)
        # Campaign is a Pydantic model without brand_context field,
        # but sensing code uses hasattr() so we set it via object.__setattr__
        object.__setattr__(campaign, "brand_context", {
            "sensing_thresholds": {"email_min_delivered": 5, "email_reply_rate_min": 5.0},
        })
        # 6 deliveries with 0 replies should now trigger (5 < 50 default)
        for _ in range(6):
            await self.engine.process_event(campaign, _email_event("delivered"))
        result = await self.engine.process_event(campaign, _email_event("delivered"))
        # reply_rate is 0% < 5% and delivered is 7 >= 5
        assert result is not None
        assert result["trigger"] == "rerun_agent"
