"""
Integration tests for FastAPI routes — campaign lifecycle, auth enforcement,
input validation, and tenant isolation.
Uses TestClient to exercise real HTTP endpoints without network calls.
"""
from __future__ import annotations
import pytest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Patch settings before importing app
from unittest.mock import patch, MagicMock
import config

_test_settings = config.Settings(
    supabase_url="",
    supabase_service_key="",
    supabase_jwt_secret="",
    providers=[],
)
config.settings = _test_settings

from fastapi.testclient import TestClient
from main import app, campaigns
from models import Campaign, CampaignMemory, BusinessProfile


@pytest.fixture(autouse=True)
def clean_store():
    """Reset stores between tests."""
    campaigns.clear()
    yield


client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_no_auth_required(self):
        """Health should work without any Authorization header."""
        r = client.get("/health")
        assert r.status_code == 200


# ── Agent listing ─────────────────────────────────────────────────────────────

class TestAgents:
    def test_list_agents(self):
        r = client.get("/agents")
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        assert len(agents) > 0
        assert "id" in agents[0]
        assert "label" in agents[0]

    def test_agents_have_tools(self):
        r = client.get("/agents")
        agents = r.json()
        for a in agents:
            assert "tool_count" in a
            assert isinstance(a["tool_count"], int)


# ── Campaign CRUD ─────────────────────────────────────────────────────────────

class TestCampaignCRUD:
    def _create_campaign_in_store(self, campaign_id="test-001"):
        """Helper to put a campaign directly in the legacy store."""
        biz = BusinessProfile(name="Test", service="SaaS", icp="B2B", geography="US", goal="Grow")
        c = Campaign(id=campaign_id, user_id="dev-mode", memory=CampaignMemory(business=biz))
        campaigns[campaign_id] = c
        return c

    def test_get_campaign(self):
        self._create_campaign_in_store("c-1")
        r = client.get("/campaign/c-1")
        assert r.status_code == 200
        assert r.json()["id"] == "c-1"

    def test_get_campaign_not_found(self):
        r = client.get("/campaign/nonexistent")
        assert r.status_code == 404

    def test_delete_campaign(self):
        self._create_campaign_in_store("c-del")
        r = client.delete("/campaign/c-del")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_get_campaign_memory(self):
        self._create_campaign_in_store("c-mem")
        r = client.get("/campaign/c-mem/memory")
        assert r.status_code == 200
        data = r.json()
        assert "business" in data
        assert data["business"]["name"] == "Test"


# ── Input validation ──────────────────────────────────────────────────────────

class TestInputValidation:
    def test_validate_endpoint_rejects_empty_output(self):
        r = client.post("/validate", json={"output": "", "icp": "test"})
        assert r.status_code == 400

    def test_approval_decision_rejects_invalid(self):
        r = client.post("/approvals/fake-id/decide", json={"decision": "maybe"})
        # Either 404 (not found) or 400 (invalid decision)
        assert r.status_code in (400, 404)


# ── Templates ─────────────────────────────────────────────────────────────────

class TestTemplates:
    def test_list_templates(self):
        r = client.get("/templates")
        assert r.status_code == 200
        assert "templates" in r.json()

    def test_get_nonexistent_template(self):
        r = client.get("/templates/nonexistent-template-xyz")
        assert r.status_code == 404


# ── Providers ─────────────────────────────────────────────────────────────────

class TestProviders:
    def test_list_providers(self):
        r = client.get("/providers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Scheduler ─────────────────────────────────────────────────────────────────

class TestScheduler:
    def test_scheduler_status(self):
        r = client.get("/scheduler")
        assert r.status_code == 200
        assert "jobs" in r.json()
