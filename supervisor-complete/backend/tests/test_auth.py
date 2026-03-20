"""Tests for authentication — JWT validation, input sanitization, safe_setattr."""
from __future__ import annotations
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth import validate_id, validate_campaign_id, safe_setattr, MEMORY_WRITABLE_FIELDS
from models import CampaignMemory, BusinessProfile
from fastapi import HTTPException


# ── Input validation ──────────────────────────────────────────────────────────

class TestValidateId:
    def test_valid_alphanumeric(self):
        assert validate_id("abc-123_XYZ") == "abc-123_XYZ"

    def test_empty_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_id("")
        assert exc.value.status_code == 400

    def test_too_long_raises(self):
        with pytest.raises(HTTPException):
            validate_id("a" * 200)

    def test_special_chars_rejected(self):
        with pytest.raises(HTTPException):
            validate_id("../../etc/passwd")

    def test_sql_injection_rejected(self):
        with pytest.raises(HTTPException):
            validate_id("'; DROP TABLE users; --")

    def test_spaces_rejected(self):
        with pytest.raises(HTTPException):
            validate_id("hello world")


class TestValidateCampaignId:
    def test_valid_uuid(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        assert validate_campaign_id(uid) == uid

    def test_valid_simple_id(self):
        assert validate_campaign_id("test-campaign-001") == "test-campaign-001"

    def test_empty_raises(self):
        with pytest.raises(HTTPException):
            validate_campaign_id("")

    def test_injection_raises(self):
        with pytest.raises(HTTPException):
            validate_campaign_id("x; rm -rf /")


# ── safe_setattr ──────────────────────────────────────────────────────────────

class TestSafeSetattr:
    def test_allowed_field_updated(self):
        biz = BusinessProfile(name="X", service="Y", icp="Z", geography="US", goal="G")
        mem = CampaignMemory(business=biz)
        assert safe_setattr(mem, "prospects", "new data", MEMORY_WRITABLE_FIELDS)
        assert mem.prospects == "new data"

    def test_disallowed_field_rejected(self):
        biz = BusinessProfile(name="X", service="Y", icp="Z", geography="US", goal="G")
        mem = CampaignMemory(business=biz)
        assert safe_setattr(mem, "__class__", "hacked", MEMORY_WRITABLE_FIELDS) is False

    def test_business_field_rejected(self):
        """Prevent overwriting the business profile via memory update."""
        biz = BusinessProfile(name="X", service="Y", icp="Z", geography="US", goal="G")
        mem = CampaignMemory(business=biz)
        assert safe_setattr(mem, "business", {"name": "hacked"}, MEMORY_WRITABLE_FIELDS) is False

    def test_nonexistent_field_rejected(self):
        biz = BusinessProfile(name="X", service="Y", icp="Z", geography="US", goal="G")
        mem = CampaignMemory(business=biz)
        assert safe_setattr(mem, "totally_fake_field", "x", MEMORY_WRITABLE_FIELDS) is False
