"""
Omni OS Backend — Local-First / On-Prem Deployment Support
Enables air-gapped and self-hosted deployments with local LLM support.
Competes with OpenClaw (local-first), Poolside (air-gap), NemoClaw (enterprise on-prem).
"""
from __future__ import annotations
import os
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.onprem")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class DeploymentMode(BaseModel):
    """Current deployment configuration."""
    mode: str = "cloud"              # cloud | hybrid | onprem | airgap
    data_residency: str = "us"       # us | eu | custom
    llm_routing: str = "cloud"       # cloud | local | hybrid
    storage_backend: str = "supabase"  # supabase | postgres | sqlite | filesystem
    telemetry_enabled: bool = True
    external_api_allowed: bool = True
    local_llm_endpoint: str = ""     # e.g. http://localhost:11434 (Ollama)
    local_llm_model: str = ""        # e.g. llama3.1:70b


class LocalLLMConfig(BaseModel):
    """Configuration for local/self-hosted LLM providers."""
    name: str
    endpoint: str                     # http://localhost:11434/v1
    model: str                        # llama3.1:70b, mixtral, etc.
    api_format: str = "openai"       # openai | ollama | vllm | tgi
    max_tokens: int = 4096
    context_window: int = 8192
    supports_tools: bool = False
    supports_streaming: bool = True
    gpu_required: bool = True
    enabled: bool = True


class DataRetentionPolicy(BaseModel):
    """Controls where and how long data is stored."""
    store_prompts: bool = True
    store_responses: bool = True
    store_tool_results: bool = True
    retention_days: int = 90          # 0 = indefinite
    encrypt_at_rest: bool = False
    pii_fields_to_redact: list[str] = []
    export_format: str = "json"      # json | csv | parquet


# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL LLM REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

# Pre-configured local LLM options
LOCAL_LLM_PRESETS = {
    "ollama_llama3": LocalLLMConfig(
        name="Ollama Llama 3.1", endpoint="http://localhost:11434/v1",
        model="llama3.1:70b", api_format="openai",
        max_tokens=4096, context_window=131072,
        supports_tools=True, supports_streaming=True,
    ),
    "ollama_mixtral": LocalLLMConfig(
        name="Ollama Mixtral", endpoint="http://localhost:11434/v1",
        model="mixtral:8x22b", api_format="openai",
        max_tokens=4096, context_window=65536,
        supports_tools=True, supports_streaming=True,
    ),
    "ollama_qwen": LocalLLMConfig(
        name="Ollama Qwen 2.5", endpoint="http://localhost:11434/v1",
        model="qwen2.5:72b", api_format="openai",
        max_tokens=4096, context_window=131072,
        supports_tools=True, supports_streaming=True,
    ),
    "vllm_custom": LocalLLMConfig(
        name="vLLM Custom", endpoint="http://localhost:8000/v1",
        model="custom", api_format="openai",
        max_tokens=4096, context_window=32768,
        supports_tools=True, supports_streaming=True,
    ),
    "tgi_custom": LocalLLMConfig(
        name="TGI Custom", endpoint="http://localhost:8080/v1",
        model="custom", api_format="openai",
        max_tokens=2048, context_window=8192,
        supports_tools=False, supports_streaming=True,
    ),
    # NVIDIA TensorRT-optimized inference
    "tensorrt_llama3": LocalLLMConfig(
        name="TensorRT Llama 3.1", endpoint="http://localhost:8001/v2/models/llama3/infer",
        model="llama3.1-70b-trt", api_format="openai",
        max_tokens=4096, context_window=131072,
        supports_tools=True, supports_streaming=True,
        gpu_required=True,
    ),
    # NVIDIA Triton local server
    "triton_local": LocalLLMConfig(
        name="Triton Local", endpoint="http://localhost:8001/v2",
        model="ensemble", api_format="openai",
        max_tokens=4096, context_window=32768,
        supports_tools=True, supports_streaming=True,
        gpu_required=True,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class OnPremManager:
    """
    Manages local-first and on-prem deployment configurations.
    Handles local LLM routing, data residency, and air-gap mode.
    """

    def __init__(self):
        self._mode = self._detect_mode()
        self._local_llms: dict[str, LocalLLMConfig] = {}
        self._retention = DataRetentionPolicy()
        self._feature_overrides: dict[str, bool] = {}

    def _detect_mode(self) -> DeploymentMode:
        """Auto-detect deployment mode from environment."""
        mode_str = os.getenv("DEPLOYMENT_MODE", "cloud")
        local_llm = os.getenv("LOCAL_LLM_ENDPOINT", "")
        storage = os.getenv("STORAGE_BACKEND", "supabase")

        mode = DeploymentMode(
            mode=mode_str,
            data_residency=os.getenv("DATA_RESIDENCY", "us"),
            llm_routing="local" if local_llm else ("hybrid" if mode_str == "hybrid" else "cloud"),
            storage_backend=storage,
            telemetry_enabled=os.getenv("TELEMETRY_ENABLED", "true").lower() == "true",
            external_api_allowed=mode_str != "airgap",
            local_llm_endpoint=local_llm,
            local_llm_model=os.getenv("LOCAL_LLM_MODEL", ""),
        )

        logger.info(f"Deployment mode: {mode.mode}, LLM routing: {mode.llm_routing}, Storage: {mode.storage_backend}")
        return mode

    @property
    def deployment_mode(self) -> DeploymentMode:
        return self._mode

    @property
    def is_airgapped(self) -> bool:
        return self._mode.mode == "airgap"

    @property
    def is_onprem(self) -> bool:
        return self._mode.mode in ("onprem", "airgap")

    @property
    def allows_external_apis(self) -> bool:
        return self._mode.external_api_allowed

    def configure_mode(self, mode: str, **kwargs) -> DeploymentMode:
        """Update deployment mode and settings."""
        self._mode.mode = mode
        for k, v in kwargs.items():
            if hasattr(self._mode, k):
                setattr(self._mode, k, v)

        # Enforce air-gap restrictions
        if mode == "airgap":
            self._mode.external_api_allowed = False
            self._mode.telemetry_enabled = False
            self._mode.llm_routing = "local"

        logger.info(f"Deployment mode updated: {self._mode.mode}")
        return self._mode

    def register_local_llm(self, config: LocalLLMConfig) -> LocalLLMConfig:
        """Register a local LLM endpoint."""
        self._local_llms[config.name] = config
        logger.info(f"Registered local LLM: {config.name} @ {config.endpoint}")
        return config

    def register_preset(self, preset_name: str) -> Optional[LocalLLMConfig]:
        """Register a pre-configured local LLM."""
        preset = LOCAL_LLM_PRESETS.get(preset_name)
        if preset:
            self._local_llms[preset.name] = preset
            logger.info(f"Registered preset: {preset_name}")
        return preset

    def get_local_llms(self) -> list[LocalLLMConfig]:
        return list(self._local_llms.values())

    def get_provider_config_for_local(self, llm_name: str = None) -> Optional[dict]:
        """
        Generate a ProviderConfig-compatible dict for a local LLM.
        Can be added to the ModelRouter's adapter list.
        """
        if llm_name:
            llm = self._local_llms.get(llm_name)
        elif self._local_llms:
            llm = list(self._local_llms.values())[0]
        else:
            return None

        if not llm:
            return None

        return {
            "name": f"local_{llm.name}",
            "api_key": "local",
            "base_url": llm.endpoint.rstrip("/v1"),
            "default_model": llm.model,
            "fast_model": llm.model,
            "strong_model": llm.model,
            "enabled": llm.enabled,
            "priority": -1,  # Highest priority
            "timeout": 300,  # Local models may be slower
        }

    def set_retention_policy(self, policy: DataRetentionPolicy):
        self._retention = policy
        logger.info(f"Data retention updated: {policy.retention_days} days, encrypt={policy.encrypt_at_rest}")

    def get_retention_policy(self) -> DataRetentionPolicy:
        return self._retention

    def check_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed in current deployment mode."""
        if self._mode.external_api_allowed:
            return True

        # In air-gap mode, only allow tools that don't call external APIs
        LOCAL_SAFE_TOOLS = {
            "store_data", "read_data", "generate_document",
            "generate_pdf_report", "create_survey", "score_lead",
        }
        return tool_name in LOCAL_SAFE_TOOLS

    def get_blocked_tools(self) -> list[str]:
        """Get list of tools blocked by current deployment mode."""
        if self._mode.external_api_allowed:
            return []

        # All tools that require external API calls
        EXTERNAL_TOOLS = [
            "web_search", "web_scrape", "company_research", "find_contacts",
            "verify_email", "enrich_company", "enrich_person", "send_email",
            "post_twitter", "post_linkedin", "post_instagram", "send_sms",
            "make_phone_call", "deploy_to_vercel", "deploy_to_cloudflare",
            "create_meta_ad_campaign", "create_google_ads_campaign",
            "seo_keyword_research", "generate_image", "publish_to_cms",
            "send_for_signature", "check_page_speed",
        ]
        return EXTERNAL_TOOLS

    def export_config(self) -> dict:
        """Export current on-prem configuration for backup/replication."""
        return {
            "deployment_mode": self._mode.model_dump(),
            "local_llms": {k: v.model_dump() for k, v in self._local_llms.items()},
            "retention_policy": self._retention.model_dump(),
            "feature_overrides": self._feature_overrides,
            "exported_at": datetime.utcnow().isoformat(),
        }

    def import_config(self, config: dict):
        """Import on-prem configuration."""
        if "deployment_mode" in config:
            self._mode = DeploymentMode(**config["deployment_mode"])
        if "local_llms" in config:
            for name, llm_data in config["local_llms"].items():
                self._local_llms[name] = LocalLLMConfig(**llm_data)
        if "retention_policy" in config:
            self._retention = DataRetentionPolicy(**config["retention_policy"])
        logger.info("On-prem configuration imported")

    def health_check(self) -> dict:
        """Check health of on-prem components."""
        return {
            "mode": self._mode.mode,
            "llm_routing": self._mode.llm_routing,
            "local_llms_registered": len(self._local_llms),
            "local_llms": [
                {"name": l.name, "endpoint": l.endpoint, "model": l.model, "enabled": l.enabled}
                for l in self._local_llms.values()
            ],
            "external_apis_allowed": self._mode.external_api_allowed,
            "storage_backend": self._mode.storage_backend,
            "data_residency": self._mode.data_residency,
            "telemetry": self._mode.telemetry_enabled,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

onprem = OnPremManager()
