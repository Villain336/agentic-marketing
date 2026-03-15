"""
Supervisor Backend — Configuration
Environment-based settings with multi-provider support.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProviderConfig:
    """Single LLM provider configuration."""
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: str = ""
    fast_model: str = ""
    enabled: bool = False
    priority: int = 99
    timeout: int = 120
    max_retries: int = 2

    def __post_init__(self):
        self.enabled = bool(self.api_key)


@dataclass
class Settings:
    """Application settings loaded from environment."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: ["*"])

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    providers: list = field(default_factory=list)

    max_agent_iterations: int = 25
    max_agent_runtime: int = 300
    default_max_tokens: int = 4096

    apollo_api_key: str = ""
    sendgrid_api_key: str = ""
    hunter_api_key: str = ""
    serper_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        providers = []

        providers.append(ProviderConfig(
            name="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url="https://api.anthropic.com",
            default_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            fast_model=os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5-20251001"),
            priority=1,
            timeout=int(os.getenv("ANTHROPIC_TIMEOUT", "120")),
        ))

        providers.append(ProviderConfig(
            name="openai",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url="https://api.openai.com",
            default_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            fast_model=os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
            priority=2,
            timeout=int(os.getenv("OPENAI_TIMEOUT", "120")),
        ))

        providers.append(ProviderConfig(
            name="google",
            api_key=os.getenv("GOOGLE_API_KEY", ""),
            base_url="https://generativelanguage.googleapis.com",
            default_model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
            fast_model=os.getenv("GOOGLE_FAST_MODEL", "gemini-2.0-flash-lite"),
            priority=3,
            timeout=int(os.getenv("GOOGLE_TIMEOUT", "120")),
        ))

        providers.sort(key=lambda p: p.priority)

        return cls(
            debug=os.getenv("DEBUG", "").lower() in ("1", "true"),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
            providers=providers,
            max_agent_iterations=int(os.getenv("MAX_AGENT_ITERATIONS", "25")),
            max_agent_runtime=int(os.getenv("MAX_AGENT_RUNTIME", "300")),
            apollo_api_key=os.getenv("APOLLO_API_KEY", ""),
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
            serper_api_key=os.getenv("SERPER_API_KEY", ""),
        )

    @property
    def active_providers(self) -> list:
        return [p for p in self.providers if p.enabled]

    @property
    def primary_provider(self) -> Optional[ProviderConfig]:
        active = self.active_providers
        return active[0] if active else None


settings = Settings.from_env()
