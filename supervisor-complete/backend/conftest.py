"""
Shared pytest fixtures for Supervisor backend tests.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure the backend package root is on sys.path so bare imports work.
sys.path.insert(0, os.path.dirname(__file__))


# ── Mock settings (empty API keys → all DB/HTTP paths short-circuit) ─────────

class _MockSettings:
    """Minimal stand-in for config.settings with empty keys."""
    supabase_url = ""
    supabase_key = ""
    supabase_anon_key = ""
    supabase_service_key = ""
    supabase_jwt_secret = ""
    providers = []
    debug = False


@pytest.fixture()
def mock_settings(monkeypatch):
    """Patch ``config.settings`` everywhere so nothing reaches the network."""
    s = _MockSettings()
    monkeypatch.setattr("config.settings", s)
    return s


# ── Business / Campaign fixtures ─────────────────────────────────────────────

@pytest.fixture()
def business_profile():
    from models import BusinessProfile
    return BusinessProfile(
        name="Acme Corp",
        service="Marketing Automation SaaS",
        icp="B2B SaaS founders, 10-50 employees",
        geography="United States",
        goal="Acquire 50 paying customers in 90 days",
        entity_type="llc",
        state_of_formation="Delaware",
        founder_title="Managing Member",
        industry="marketing agency",
    )


@pytest.fixture()
def campaign(business_profile):
    from models import Campaign, CampaignMemory
    mem = CampaignMemory(
        business=business_profile,
        prospects="Alice (CTO, Acme)\nBob (VP Sales, Globex)",
        prospect_count=10,
        email_sequence="Subject: Quick question\nBody: ...",
        content_strategy="Publish weekly blog posts on growth hacking",
        social_calendar="Mon: LinkedIn, Wed: Twitter, Fri: Newsletter",
        ad_package="Meta + Google Display",
        cs_system="Onboarding flow + NPS survey",
        site_launch_brief="Landing page with hero, features, pricing, CTA",
        legal_playbook="Privacy policy covering GDPR, terms of service, compliance checklist, contract templates, IP assignment, liability waiver, NDA template",
        gtm_strategy="Product-led growth with free trial funnel",
        newsletter_system="Weekly digest via ConvertKit",
        ppc_playbook="Google Ads: branded + competitor keywords",
    )
    return Campaign(id="test-campaign-001", user_id="user-1", memory=mem)


@pytest.fixture()
def performance_event():
    from models import PerformanceEvent
    return PerformanceEvent(
        campaign_id="test-campaign-001",
        source="sendgrid",
        event_type="email",
        data={"event": "delivered", "variant": "default"},
    )
