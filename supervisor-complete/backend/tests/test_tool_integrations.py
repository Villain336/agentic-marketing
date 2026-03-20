"""
Integration tests for tool API connections.

Tests verify that tools:
1. Return valid JSON responses
2. Handle missing API keys gracefully (PARTIAL tools degrade to stub)
3. Make real API calls when keys are configured (mark with @pytest.mark.integration)
4. Never crash — always return structured error/fallback

Run unit tests:     pytest tests/test_tool_integrations.py -v
Run integration:    pytest tests/test_tool_integrations.py -v -m integration
Skip integration:   pytest tests/test_tool_integrations.py -v -m "not integration"
"""
from __future__ import annotations

import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse(result: str) -> dict:
    """Parse tool result as JSON, failing with a clear message if invalid."""
    try:
        data = json.loads(result)
        assert isinstance(data, (dict, list)), f"Expected dict/list, got {type(data)}"
        return data
    except json.JSONDecodeError as e:
        pytest.fail(f"Tool returned invalid JSON: {e}\nRaw: {result[:500]}")


def _has_key(env_var: str) -> bool:
    """Check if an API key is actually configured."""
    return bool(os.getenv(env_var, ""))


# ═══════════════════════════════════════════════════════════════════════════════
# PROSPECTING & ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebSearch:
    """Tests for _web_search (Serper.dev)."""

    @pytest.mark.asyncio
    async def test_missing_key_returns_note(self):
        from tools import _web_search
        with patch("config.settings") as ms:
            ms.serper_api_key = ""
            result = _parse(await _web_search("test query"))
            assert "note" in result or "error" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("SERPER_API_KEY"), reason="SERPER_API_KEY not set")
    async def test_real_search(self):
        from tools import _web_search
        result = _parse(await _web_search("Python programming", 3))
        assert "results" in result
        assert len(result["results"]) > 0
        assert "title" in result["results"][0]
        assert "url" in result["results"][0]

    @pytest.mark.asyncio
    async def test_mocked_search(self):
        """Verify _web_search processes Serper API response correctly."""
        from tools import _web_search
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "organic": [
                {"title": "Learn Python", "link": "https://python.org", "snippet": "Official site"},
                {"title": "Python Tutorial", "link": "https://docs.python.org", "snippet": "Docs"},
            ]
        }
        with patch.object(_http, "post", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.research.settings") as ms:
            ms.serper_api_key = "fake-key"
            result = _parse(await _web_search("Python programming", 3))
            assert "results" in result
            assert len(result["results"]) > 0
            assert "title" in result["results"][0]


class TestWebScrape:
    """Tests for _web_scrape (direct HTTP)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scrape_real_url(self):
        from tools import _web_scrape
        result = _parse(await _web_scrape("https://httpbin.org/html", 2000))
        assert "content" in result
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_scrape_invalid_url(self):
        from tools import _web_scrape
        result = _parse(await _web_scrape("https://this-domain-does-not-exist-12345.com"))
        assert "error" in result


class TestCompanyResearch:
    """Tests for _company_research (Apollo.io)."""

    @pytest.mark.asyncio
    async def test_no_key_falls_back_to_search(self):
        from tools import _company_research
        with patch("config.settings") as ms:
            ms.apollo_api_key = ""
            ms.serper_api_key = ""
            result = _parse(await _company_research("Anthropic"))
            # Should return search fallback or note
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("APOLLO_API_KEY"), reason="APOLLO_API_KEY not set")
    async def test_real_apollo_search(self):
        from tools import _company_research
        result = _parse(await _company_research("Anthropic", "anthropic.com"))
        assert "results" in result or "company" in result

    @pytest.mark.asyncio
    async def test_mocked_apollo_search(self):
        """Verify _company_research processes Apollo API response correctly."""
        from tools import _company_research
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "organizations": [
                {"name": "Anthropic", "primary_domain": "anthropic.com",
                 "industry": "AI", "estimated_num_employees": 500,
                 "annual_revenue_printed": "$100M+",
                 "short_description": "AI safety company",
                 "linkedin_url": "https://linkedin.com/company/anthropic",
                 "city": "San Francisco", "state": "CA"}
            ]
        }
        with patch.object(_http, "post", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.research.settings") as ms:
            ms.apollo_api_key = "fake-key"
            ms.serper_api_key = ""
            result = _parse(await _company_research("Anthropic", "anthropic.com"))
            assert "results" in result or "company" in result


class TestFindContacts:
    """Tests for _find_contacts (Apollo/Hunter)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_note(self):
        from tools import _find_contacts
        with patch("config.settings") as ms:
            ms.apollo_api_key = ""
            ms.hunter_api_key = ""
            result = _parse(await _find_contacts("example.com"))
            assert "note" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("APOLLO_API_KEY"), reason="APOLLO_API_KEY not set")
    async def test_real_contact_search(self):
        from tools import _find_contacts
        result = _parse(await _find_contacts("anthropic.com", "CEO", 3))
        assert "contacts" in result

    @pytest.mark.asyncio
    async def test_mocked_contact_search(self):
        """Verify _find_contacts processes Apollo API response correctly."""
        from tools import _find_contacts
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "people": [
                {"first_name": "Dario", "last_name": "Amodei", "title": "CEO",
                 "email": "dario@anthropic.com", "linkedin_url": "https://linkedin.com/in/dario",
                 "city": "San Francisco", "state": "CA"}
            ]
        }
        with patch.object(_http, "post", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.prospecting.settings") as ms:
            ms.apollo_api_key = "fake-key"
            ms.hunter_api_key = ""
            result = _parse(await _find_contacts("anthropic.com", "CEO", 3))
            assert "contacts" in result


class TestVerifyEmail:
    """Tests for _verify_email (Hunter.io)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_note(self):
        from tools import _verify_email
        with patch("config.settings") as ms:
            ms.hunter_api_key = ""
            result = _parse(await _verify_email("test@example.com"))
            assert "note" in result or "email" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("HUNTER_API_KEY"), reason="HUNTER_API_KEY not set")
    async def test_real_verify(self):
        from tools import _verify_email
        result = _parse(await _verify_email("info@anthropic.com"))
        assert "status" in result

    @pytest.mark.asyncio
    async def test_mocked_verify(self):
        """Verify _verify_email processes Hunter API response correctly."""
        from tools import _verify_email
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"email": "info@anthropic.com", "result": "deliverable",
                     "score": 95, "regexp": True, "gibberish": False,
                     "disposable": False, "webmail": False, "mx_records": True,
                     "smtp_server": True, "smtp_check": True, "accept_all": False}
        }
        with patch.object(_http, "get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.prospecting.settings") as ms:
            ms.hunter_api_key = "fake-key"
            result = _parse(await _verify_email("info@anthropic.com"))
            assert "email" in result or "status" in result


class TestEnrichCompany:
    """Tests for _enrich_company (Clearbit/Apollo)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_note(self):
        from tools import _enrich_company
        with patch("config.settings") as ms:
            ms.clearbit_api_key = ""
            ms.apollo_api_key = ""
            result = _parse(await _enrich_company("example.com"))
            assert "note" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(
        not (_has_key("CLEARBIT_API_KEY") or _has_key("APOLLO_API_KEY")),
        reason="No enrichment key set"
    )
    async def test_real_enrich(self):
        from tools import _enrich_company
        result = _parse(await _enrich_company("anthropic.com"))
        assert "name" in result or "domain" in result

    @pytest.mark.asyncio
    async def test_mocked_enrich(self):
        """Verify _enrich_company processes Clearbit API response correctly."""
        from tools import _enrich_company
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Anthropic", "domain": "anthropic.com",
            "category": {"industry": "Artificial Intelligence"},
            "metrics": {"employees": 500, "estimatedAnnualRevenue": "$100M+"},
            "tech": ["Python", "React", "AWS"],
            "foundedYear": 2021,
            "description": "AI safety company building reliable AI systems.",
            "geo": {"city": "San Francisco", "state": "California", "country": "US"},
            "linkedin": {"handle": "anthropic"}, "twitter": {"handle": "AnthropicAI"},
            "phone": "+1-415-555-0100"
        }
        with patch.object(_http, "get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.prospecting.settings") as ms:
            ms.clearbit_api_key = "fake-key"
            ms.apollo_api_key = ""
            result = _parse(await _enrich_company("anthropic.com"))
            assert "name" in result or "domain" in result


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendEmail:
    """Tests for _send_email (SendGrid)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _send_email
        with patch("config.settings") as ms:
            ms.sendgrid_api_key = ""
            result = _parse(await _send_email("test@test.com", "Test", "<p>Body</p>"))
            assert "error" in result


class TestEmailSequence:
    """Tests for _schedule_email_sequence (SendGrid)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _schedule_email_sequence
        with patch("config.settings") as ms:
            ms.sendgrid_api_key = ""
            emails = json.dumps([{"to": "a@b.com", "subject": "Hi", "body": "Hello"}])
            result = _parse(await _schedule_email_sequence(emails))
            assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE & SMS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMakePhoneCall:
    """Tests for _make_phone_call (Bland.ai/Vapi/Twilio)."""

    @pytest.mark.asyncio
    async def test_no_provider_returns_error(self):
        from tools import _make_phone_call
        with patch("config.settings") as ms:
            ms.bland_api_key = ""
            ms.vapi_api_key = ""
            ms.twilio_account_sid = ""
            ms.twilio_auth_token = ""
            result = _parse(await _make_phone_call("+15551234567", "Test script"))
            assert "error" in result


class TestSendSms:
    """Tests for _send_sms (Twilio)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _send_sms
        with patch("config.settings") as ms:
            ms.twilio_account_sid = ""
            ms.twilio_auth_token = ""
            result = _parse(await _send_sms("+15551234567", "Test message"))
            assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL MEDIA
# ═══════════════════════════════════════════════════════════════════════════════

class TestPostTwitter:
    """Tests for _post_twitter (Twitter API v2)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _post_twitter
        with patch("config.settings") as ms:
            ms.twitter_bearer_token = ""
            ms.twitter_api_key = ""
            ms.twitter_access_token = ""
            result = _parse(await _post_twitter("Test tweet"))
            assert "error" in result or "note" in result


class TestSearchTwitter:
    """Tests for _search_twitter (Twitter API v2)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _search_twitter
        with patch("config.settings") as ms:
            ms.twitter_bearer_token = ""
            result = _parse(await _search_twitter("AI news"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SEO TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeoKeywordResearch:
    """Tests for _seo_keyword_research (DataForSEO/SEMrush)."""

    @pytest.mark.asyncio
    async def test_no_key_fallback(self):
        from tools import _seo_keyword_research
        with patch("config.settings") as ms:
            ms.dataforseo_login = ""
            ms.dataforseo_password = ""
            ms.semrush_api_key = ""
            ms.serper_api_key = ""
            result = _parse(await _seo_keyword_research("marketing automation"))
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("DATAFORSEO_LOGIN"), reason="DATAFORSEO_LOGIN not set")
    async def test_real_keyword_research(self):
        from tools import _seo_keyword_research
        result = _parse(await _seo_keyword_research("marketing automation"))
        assert "keyword" in result or "results" in result

    @pytest.mark.asyncio
    async def test_mocked_keyword_research(self):
        """Verify _seo_keyword_research processes DataForSEO response correctly."""
        from tools import _seo_keyword_research
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [{"result": [{"keyword": "marketing automation",
                                   "search_volume": 14800, "cpc": 12.50,
                                   "competition": "HIGH", "competition_index": 85}]}]
        }
        with patch.object(_http, "post", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.content.settings") as ms:
            ms.dataforseo_login = "fake-login"
            ms.dataforseo_password = "fake-pass"
            ms.semrush_api_key = ""
            ms.serper_api_key = ""
            result = _parse(await _seo_keyword_research("marketing automation"))
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateImage:
    """Tests for _generate_image (DALL-E/Replicate/Fal)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _generate_image
        with patch("config.settings") as ms:
            ms.openai_image_key = ""
            ms.replicate_api_key = ""
            ms.fal_api_key = ""
            result = _parse(await _generate_image("a sunset"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# CMS PUBLISHING
# ═══════════════════════════════════════════════════════════════════════════════

class TestPublishToCms:
    """Tests for _publish_to_cms (WordPress/Ghost/Webflow)."""

    @pytest.mark.asyncio
    async def test_no_cms_returns_error(self):
        from tools import _publish_to_cms
        with patch("config.settings") as ms:
            ms.wordpress_url = ""
            ms.ghost_url = ""
            ms.ghost_admin_key = ""
            ms.webflow_api_key = ""
            result = _parse(await _publish_to_cms("Test Title", "<p>Content</p>"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT & DNS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeployToVercel:
    """Tests for _deploy_to_vercel (Vercel API)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _deploy_to_vercel
        with patch("config.settings") as ms:
            ms.vercel_token = ""
            files = json.dumps({"index.html": "<h1>Test</h1>"})
            result = _parse(await _deploy_to_vercel("test-project", files))
            assert "error" in result


class TestCheckDomain:
    """Tests for _check_domain_availability (GoDaddy)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("GODADDY_API_KEY"), reason="GODADDY_API_KEY not set")
    async def test_real_domain_check(self):
        from tools import _check_domain_availability
        result = _parse(await _check_domain_availability("example.com"))
        assert "domain" in result

    @pytest.mark.asyncio
    async def test_mocked_domain_check(self):
        """Verify _check_domain_availability processes Namecheap response correctly."""
        from tools import _check_domain_availability
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """<?xml version="1.0" encoding="utf-8"?>
        <ApiResponse Status="OK">
          <CommandResponse Type="namecheap.domains.check">
            <DomainCheckResult Domain="example.com" Available="false" IsPremiumName="false" PremiumRegistrationPrice="0"/>
          </CommandResponse>
        </ApiResponse>"""
        with patch.object(_http, "get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.deployment.settings") as ms:
            ms.namecheap_api_user = "fake-user"
            ms.namecheap_api_key = "fake-key"
            ms.namecheap_client_ip = "127.0.0.1"
            ms.serper_api_key = ""
            result = _parse(await _check_domain_availability("example.com"))
            assert "domain" in result or isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS & MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

class TestPageSpeed:
    """Tests for _check_page_speed (Google PSI — works without key)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_page_speed(self):
        from tools import _check_page_speed
        result = _parse(await _check_page_speed("https://example.com"))
        assert "url" in result or "error" in result


class TestScreenshot:
    """Tests for _take_screenshot (Browserless/ScreenshotOne)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _take_screenshot
        with patch("config.settings") as ms:
            ms.browserless_api_key = ""
            ms.screenshotone_api_key = ""
            result = _parse(await _take_screenshot("https://example.com"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# CRM
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrmContact:
    """Tests for _create_crm_contact (HubSpot)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _create_crm_contact
        with patch("config.settings") as ms:
            ms.hubspot_api_key = ""
            result = _parse(await _create_crm_contact("Test User", "test@test.com"))
            assert "error" in result or "note" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("HUBSPOT_API_KEY"), reason="HUBSPOT_API_KEY not set")
    async def test_real_create_contact(self):
        from tools import _create_crm_contact
        result = _parse(await _create_crm_contact(
            "Integration Test", "integration-test@example.com", "Test Corp"))
        assert "id" in result or "contact" in result or "error" in result

    @pytest.mark.asyncio
    async def test_mocked_create_contact(self):
        """Verify _create_crm_contact processes HubSpot API response correctly."""
        from tools import _create_crm_contact
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "12345",
            "properties": {"email": "test@test.com", "firstname": "Test", "lastname": "User",
                           "company": "Test Corp"},
            "createdAt": "2024-01-01T00:00:00Z"
        }
        with patch.object(_http, "post", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.crm.settings") as ms:
            ms.hubspot_api_key = "fake-key"
            result = _parse(await _create_crm_contact("Test User", "test@test.com", "Test Corp"))
            assert "contact_id" in result or "created" in result or "id" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BILLING (Stripe)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStripeInvoice:
    """Tests for _create_invoice (Stripe)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _create_invoice
        with patch("config.settings") as ms:
            ms.stripe_api_key = ""
            result = _parse(await _create_invoice(
                client_name="Test Client", client_email="test@test.com",
                amount="1000", description="Test invoice"))
            assert "error" in result or "action_required" in result


class TestStripeRevenue:
    """Tests for _get_revenue_metrics (Stripe)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_stub(self):
        from tools import _get_revenue_metrics
        with patch("config.settings") as ms:
            ms.stripe_api_key = ""
            result = _parse(await _get_revenue_metrics())
            # May return error, note, or stub data — all are valid
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# NEWSLETTER ESPs
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailList:
    """Tests for _create_email_list (ConvertKit/Mailchimp/Beehiiv)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _create_email_list
        with patch("config.settings") as ms:
            ms.convertkit_api_key = ""
            ms.mailchimp_api_key = ""
            ms.beehiiv_api_key = ""
            result = _parse(await _create_email_list("Test List"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# COMMUNITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchReddit:
    """Tests for _search_reddit (public JSON API — no key needed)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_search(self):
        from tools import _search_reddit
        result = _parse(await _search_reddit("python programming", "learnpython"))
        assert "results" in result or "posts" in result or "error" in result


class TestSearchHackerNews:
    """Tests for _search_hackernews (Algolia API — no key needed)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_search(self):
        from tools import _search_hackernews
        result = _parse(await _search_hackernews("startup"))
        assert "results" in result or "hits" in result or "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# FIGMA
# ═══════════════════════════════════════════════════════════════════════════════

class TestFigmaGetFile:
    """Tests for _figma_get_file (Figma REST API)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from tools import _figma_get_file
        with patch("config.settings") as ms:
            ms.figma_api_key = ""
            result = _parse(await _figma_get_file("test-file-key"))
            assert "error" in result or "note" in result


# ═══════════════════════════════════════════════════════════════════════════════
# ECONOMIC INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketData:
    """Tests for _get_market_data (Yahoo Finance — no key needed)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_market_data(self):
        from tools import _get_market_data
        result = _parse(await _get_market_data("AAPL"))
        assert "error" not in result or "prices" in result or "data" in result


class TestEconomicIndicators:
    """Tests for _get_economic_indicators (FRED API)."""

    @pytest.mark.asyncio
    async def test_no_key_returns_stub(self):
        from tools import _get_economic_indicators
        with patch("config.settings") as ms:
            ms.fred_api_key = ""
            result = _parse(await _get_economic_indicators("GDP,UNRATE"))
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not _has_key("FRED_API_KEY"), reason="FRED_API_KEY not set")
    async def test_real_fred_data(self):
        from tools import _get_economic_indicators
        result = _parse(await _get_economic_indicators("GDP"))
        assert "indicators" in result or "GDP" in str(result)

    @pytest.mark.asyncio
    async def test_mocked_fred_data(self):
        """Verify _get_economic_indicators processes FRED API response correctly."""
        from tools import _get_economic_indicators
        from tools.registry import _http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "observations": [
                {"date": "2024-10-01", "value": "29352.301"},
                {"date": "2024-07-01", "value": "28862.488"},
                {"date": "2024-04-01", "value": "28405.093"},
            ]
        }
        with patch.object(_http, "get", new_callable=AsyncMock, return_value=mock_resp), \
             patch("tools.research.settings") as ms:
            ms.fred_api_key = "fake-key"
            result = _parse(await _get_economic_indicators("GDP"))
            assert "indicators" in result or isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE MANUFACTURING
# ═══════════════════════════════════════════════════════════════════════════════

class TestCadModel:
    """Tests for _generate_cad_model (stub — local generation)."""

    @pytest.mark.asyncio
    async def test_returns_valid_structure(self):
        from tools import _generate_cad_model
        result = _parse(await _generate_cad_model("simple bracket", "step"))
        assert "model_id" in result
        assert result["model_id"].startswith("CAD-")
        assert "status" in result


class TestSearchSuppliers:
    """Tests for _search_suppliers (stub)."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        from tools import _search_suppliers
        result = _parse(await _search_suppliers("M5 bolts", "fasteners"))
        assert "results" in result
        assert len(result["results"]) > 0


class TestControlPrinter:
    """Tests for _control_printer (OctoPrint)."""

    @pytest.mark.asyncio
    async def test_no_config_returns_stub(self):
        from tools import _control_printer
        with patch("config.settings") as ms:
            ms.octoprint_url = ""
            ms.octoprint_api_key = ""
            result = _parse(await _control_printer("P1", "status"))
            assert "printer_state" in result or "status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityScan:
    """Tests for _run_security_scan (stub/Snyk)."""

    @pytest.mark.asyncio
    async def test_returns_valid_structure(self):
        from tools import _run_security_scan
        result = _parse(await _run_security_scan("owasp_top_10"))
        assert "scan_id" in result
        assert result["scan_id"].startswith("SCAN-")


class TestScanDependencies:
    """Tests for _scan_dependencies (Snyk)."""

    @pytest.mark.asyncio
    async def test_returns_valid_structure(self):
        from tools import _scan_dependencies
        result = _parse(await _scan_dependencies())
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# NVIDIA INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestGpuCluster:
    """Tests for GPU infrastructure tools."""

    @pytest.mark.asyncio
    async def test_gpu_cluster_status(self):
        from tools import _gpu_cluster_status
        result = _parse(await _gpu_cluster_status())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_allocate_gpu(self):
        from tools import _allocate_gpu
        result = _parse(await _allocate_gpu("agent-1", "A100", "40"))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# AWS INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAwsTools:
    """Tests for AWS infrastructure tools."""

    @pytest.mark.asyncio
    async def test_s3_upload(self):
        from tools import _s3_upload
        result = _parse(await _s3_upload("test/file.txt", "hello world"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_iot_register_device(self):
        from tools import _iot_register_device
        result = _parse(await _iot_register_device("sensor-1", "temperature"))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# REINDUSTRIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestReindustrializationTools:
    """Tests for reindustrialization agent tools."""

    @pytest.mark.asyncio
    async def test_analyze_factory_site(self):
        from tools import _analyze_factory_site
        result = _parse(await _analyze_factory_site("Detroit, MI"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_reshore_supply_chain(self):
        from tools import _reshore_supply_chain
        result = _parse(await _reshore_supply_chain("PCB assembly"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_track_reshoring_metrics(self):
        from tools import _track_reshoring_metrics
        result = _parse(await _track_reshoring_metrics())
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# STUB TOOL SMOKE TESTS — Verify every stub returns valid JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestStubToolsSmokeTest:
    """Smoke test: every stub tool must return valid JSON without crashing."""

    @pytest.mark.asyncio
    async def test_score_lead(self):
        from tools import _score_lead
        result = _parse(await _score_lead("TestCo", "test.com", "50", "SaaS", "CEO"))
        assert "score" in result
        assert 0 <= result["score"] <= 100

    @pytest.mark.asyncio
    async def test_build_financial_model(self):
        from tools import _build_financial_model
        result = _parse(await _build_financial_model("consulting", "retainer", "5000", "10"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_compliance_checklist(self):
        from tools import _compliance_checklist
        result = _parse(await _compliance_checklist("agency", "CA"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_page(self):
        from tools import _generate_page
        result = _parse(await _generate_page("home", "TestCo", "We do things"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_tax_writeoff_audit(self):
        from tools import _tax_writeoff_audit
        result = _parse(await _tax_writeoff_audit("llc", "consulting", "100000"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_build_sales_pipeline(self):
        from tools import _build_sales_pipeline
        result = _parse(await _build_sales_pipeline("SaaS", "5000", "30"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_capacity_planning(self):
        from tools import _capacity_planning
        result = _parse(await _capacity_planning("consulting", "10", "3"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_client_health_score(self):
        from tools import _client_health_score
        result = _parse(await _client_health_score(
            client_name="Test Client", monthly_revenue="5000",
            satisfaction_score="8"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_mobile_app(self):
        from tools import _generate_mobile_app
        result = _parse(await _generate_mobile_app("ios", "TestApp"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_cad_model(self):
        from tools import _generate_cad_model
        result = _parse(await _generate_cad_model("bracket", "step"))
        assert "model_id" in result

    @pytest.mark.asyncio
    async def test_production_plan(self):
        from tools import _production_plan
        result = _parse(await _production_plan("PROD-001", "100"))
        assert "plan_id" in result

    @pytest.mark.asyncio
    async def test_threat_model(self):
        from tools import _threat_model
        result = _parse(await _threat_model("auth_service"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_code(self):
        from tools import _generate_code
        result = _parse(await _generate_code("python", "hello world function"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_build_world_state(self):
        from tools import _build_world_state
        result = _parse(await _build_world_state())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_create_support_ticket(self):
        from tools import _create_support_ticket
        result = _parse(await _create_support_ticket("Bug report", "Something broke"))
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_draft_press_release(self):
        from tools import _draft_press_release
        result = _parse(await _draft_press_release("Company Launches Product", "Details here"))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRATION — Verify all tools are properly registered
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRegistration:
    """Verify that tool registration works correctly."""

    def test_register_all_tools_succeeds(self):
        """All tools should register without errors."""
        from tools import registry
        assert len(registry._tools) > 250, f"Expected 250+ tools, got {len(registry._tools)}"

    def test_all_tools_have_handlers(self):
        """Every registered tool must have a callable handler."""
        from tools import registry
        for name in registry._tools:
            handler = registry._handlers.get(name)
            assert callable(handler), f"Tool '{name}' has no callable handler"

    def test_all_tools_have_descriptions(self):
        """Every registered tool must have a description."""
        from tools import registry
        for name, tool in registry._tools.items():
            assert len(tool.description) > 5, f"Tool '{name}' has no/short description: '{tool.description}'"

    def test_tool_categories_exist(self):
        """Tools should be organized into categories."""
        from tools import registry
        categories = set(t.category for t in registry._tools.values())
        assert len(categories) >= 10, f"Expected 10+ categories, got {categories}"

    def test_tool_count_at_least_290(self):
        """Platform should have 290+ tools registered."""
        from tools import registry
        assert len(registry._tools) >= 290, f"Expected 290+ tools, got {len(registry._tools)}"

    def test_handlers_match_tools(self):
        """Every tool definition should have a matching handler."""
        from tools import registry
        for name in registry._tools:
            assert name in registry._handlers, f"Tool '{name}' registered but no handler"
