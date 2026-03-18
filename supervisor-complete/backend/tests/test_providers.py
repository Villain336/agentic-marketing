"""Tests for the provider / model router layer."""
from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock

from config import ProviderConfig, Settings
from providers import (
    ModelRouter,
    ProviderAdapter,
    AnthropicAdapter,
    OpenAIAdapter,
    GoogleAdapter,
    BedrockAdapter,
    ProviderError,
    AllProvidersFailedError,
)
from models import Tier


def _provider_cfg(name="test", api_key="sk-test", enabled=True, **kw) -> ProviderConfig:
    cfg = ProviderConfig(
        name=name, api_key=api_key,
        base_url="https://test.example.com",
        default_model="test-model",
        fast_model="test-fast",
        strong_model="test-strong",
        **kw,
    )
    cfg.enabled = enabled
    return cfg


# ── ModelRouter initialization ───────────────────────────────────────────────

class TestModelRouterInit:
    def test_empty_providers(self):
        with patch("providers.settings") as ms:
            ms.providers = []
            router = ModelRouter()
            assert router.adapters == []

    def test_registers_enabled_providers(self):
        with patch("providers.settings") as ms:
            ms.providers = [
                _provider_cfg(name="anthropic", api_key="sk-ant"),
                _provider_cfg(name="openai", api_key="sk-oai"),
            ]
            router = ModelRouter()
            assert len(router.adapters) == 2

    def test_skips_disabled_providers(self):
        with patch("providers.settings") as ms:
            cfg = _provider_cfg(name="anthropic", api_key="sk-ant", enabled=False)
            cfg.enabled = False
            ms.providers = [cfg]
            router = ModelRouter()
            assert len(router.adapters) == 0


# ── Provider selection / failover ────────────────────────────────────────────

class TestProviderSelection:
    def test_available_when_not_in_cooldown(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        assert adapter.is_available is True

    def test_unavailable_during_cooldown(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        adapter._mark_error("test error")
        assert adapter.is_available is False

    def test_available_after_cooldown_expires(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        adapter._mark_error("test error")
        # Force cooldown to expire
        adapter._cooldown_until = time.time() - 1
        assert adapter.is_available is True

    def test_mark_success_resets_errors(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        adapter._mark_error("err1")
        adapter._mark_error("err2")
        assert adapter._error_count == 2
        adapter._mark_success()
        assert adapter._error_count == 0
        assert adapter._last_error is None
        assert adapter.is_available is True

    def test_get_model_default(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        assert adapter.get_model(Tier.STANDARD) == "test-model"

    def test_get_model_fast(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        assert adapter.get_model(Tier.FAST) == "test-fast"

    def test_get_model_strong(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        assert adapter.get_model(Tier.STRONG) == "test-strong"

    def test_get_model_override(self):
        cfg = _provider_cfg()
        adapter = ProviderAdapter(cfg)
        assert adapter.get_model(Tier.STANDARD, model_override="custom-v2") == "custom-v2"

    def test_status_dict(self):
        cfg = _provider_cfg(name="anthropic")
        adapter = ProviderAdapter(cfg)
        s = adapter.status()
        assert s["name"] == "anthropic"
        assert s["available"] is True
        assert s["error_count"] == 0


# ── BedrockAdapter model mapping ─────────────────────────────────────────────

class TestBedrockAdapter:
    def test_model_mapping(self):
        cfg = _provider_cfg(name="bedrock")
        adapter = BedrockAdapter(cfg)
        assert "claude-sonnet" in adapter.BEDROCK_MODELS
        assert "claude-haiku" in adapter.BEDROCK_MODELS
        assert "llama3-70b" in adapter.BEDROCK_MODELS
        assert "mistral-large" in adapter.BEDROCK_MODELS

    def test_model_ids_are_valid_arn_format(self):
        cfg = _provider_cfg(name="bedrock")
        adapter = BedrockAdapter(cfg)
        for short_name, model_id in adapter.BEDROCK_MODELS.items():
            # All Bedrock model IDs should contain a provider prefix
            assert "." in model_id, f"{short_name} → {model_id} missing provider prefix"

    def test_complete_raises_without_boto3(self):
        cfg = _provider_cfg(name="bedrock")
        adapter = BedrockAdapter(cfg)
        adapter._boto_client = None  # ensure no cached client

        # If boto3 is installed, mock it away; if not, it naturally fails
        with patch.object(adapter, "_get_boto_client", return_value=None):
            with pytest.raises(ProviderError, match="boto3_unavailable"):
                import asyncio
                asyncio.get_event_loop().run_until_complete(
                    adapter.complete([{"role": "user", "content": "hi"}])
                )


# ── AllProvidersFailedError ──────────────────────────────────────────────────

class TestAllProvidersFailed:
    def test_error_message(self):
        errors = [
            ProviderError("timeout", "anthropic"),
            ProviderError("rate_limited", "openai"),
        ]
        exc = AllProvidersFailedError(errors)
        assert "anthropic" in str(exc)
        assert "openai" in str(exc)
        assert len(exc.errors) == 2


# ── ProviderConfig auto-enable ───────────────────────────────────────────────

class TestProviderConfig:
    def test_enabled_when_key_present(self):
        cfg = ProviderConfig(name="test", api_key="sk-real-key")
        assert cfg.enabled is True

    def test_disabled_when_key_empty(self):
        cfg = ProviderConfig(name="test", api_key="")
        assert cfg.enabled is False

    def test_disabled_when_key_none(self):
        cfg = ProviderConfig(name="test", api_key=None)
        assert cfg.enabled is False
