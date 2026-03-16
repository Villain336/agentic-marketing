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
    supabase_jwt_secret: str = ""

    providers: list = field(default_factory=list)

    max_agent_iterations: int = 25
    max_agent_runtime: int = 300
    default_max_tokens: int = 4096

    apollo_api_key: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    hunter_api_key: str = ""
    serper_api_key: str = ""

    # Enrichment & Prospecting
    clearbit_api_key: str = ""
    bombora_api_key: str = ""

    # Voice & SMS
    bland_api_key: str = ""
    vapi_api_key: str = ""
    vapi_phone_id: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # LinkedIn Automation
    phantombuster_api_key: str = ""
    phantombuster_linkedin_agent_id: str = ""

    # Email Warmup
    instantly_api_key: str = ""

    # Social
    twitter_bearer_token: str = ""
    twitter_api_key: str = ""
    twitter_access_token: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_ad_token: str = ""
    instagram_business_id: str = ""
    buffer_api_key: str = ""
    producthunt_token: str = ""

    # SEO & Content
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    semrush_api_key: str = ""
    replicate_api_key: str = ""
    fal_api_key: str = ""
    openai_image_key: str = ""

    # CMS
    wordpress_url: str = ""
    wordpress_user: str = ""
    wordpress_app_password: str = ""
    ghost_url: str = ""
    ghost_admin_key: str = ""
    webflow_api_key: str = ""
    webflow_blog_collection_id: str = ""

    # Plagiarism
    copyscape_user: str = ""
    copyscape_api_key: str = ""

    # Ads
    meta_access_token: str = ""
    meta_pixel_id: str = ""
    google_ads_developer_token: str = ""
    google_analytics_id: str = ""

    # Deployment & DNS
    vercel_token: str = ""
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_r2_access_key: str = ""
    cloudflare_r2_secret_key: str = ""
    cloudflare_r2_bucket: str = ""
    namecheap_api_user: str = ""
    namecheap_api_key: str = ""
    namecheap_client_ip: str = ""

    # Analytics & Monitoring
    plausible_api_key: str = ""
    google_analytics_api_key: str = ""
    google_search_console_key: str = ""
    google_psi_api_key: str = ""
    betteruptime_api_key: str = ""
    uptimerobot_api_key: str = ""
    browserless_api_key: str = ""
    screenshotone_api_key: str = ""

    # CRM & Calendar
    hubspot_api_key: str = ""
    calcom_api_key: str = ""

    # Legal & Documents
    docusign_api_key: str = ""
    pandadoc_api_key: str = ""

    # Surveys
    typeform_api_key: str = ""

    # Research
    similarweb_api_key: str = ""
    builtwith_api_key: str = ""

    # Newsletter ESPs
    convertkit_api_key: str = ""
    mailchimp_api_key: str = ""
    beehiiv_api_key: str = ""
    beehiiv_publication_id: str = ""

    # Messaging
    telegram_bot_token: str = ""
    telegram_owner_chat_id: str = ""
    slack_bot_token: str = ""
    owner_email: str = ""

    # Business Formation
    stripe_atlas_key: str = ""
    firstbase_api_key: str = ""

    # Stripe Billing
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    # Referral & Affiliate
    rewardful_api_key: str = ""
    firstpromoter_api_key: str = ""

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
            supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
            providers=providers,
            max_agent_iterations=int(os.getenv("MAX_AGENT_ITERATIONS", "25")),
            max_agent_runtime=int(os.getenv("MAX_AGENT_RUNTIME", "300")),
            # Prospecting & Enrichment
            apollo_api_key=os.getenv("APOLLO_API_KEY", ""),
            hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
            clearbit_api_key=os.getenv("CLEARBIT_API_KEY", ""),
            bombora_api_key=os.getenv("BOMBORA_API_KEY", ""),
            serper_api_key=os.getenv("SERPER_API_KEY", ""),
            # Voice & SMS
            bland_api_key=os.getenv("BLAND_API_KEY", ""),
            vapi_api_key=os.getenv("VAPI_API_KEY", ""),
            vapi_phone_id=os.getenv("VAPI_PHONE_ID", ""),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_phone_number=os.getenv("TWILIO_PHONE_NUMBER", ""),
            # LinkedIn Automation
            phantombuster_api_key=os.getenv("PHANTOMBUSTER_API_KEY", ""),
            phantombuster_linkedin_agent_id=os.getenv("PHANTOMBUSTER_LINKEDIN_AGENT_ID", ""),
            # Email
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            sendgrid_from_email=os.getenv("SENDGRID_FROM_EMAIL", ""),
            instantly_api_key=os.getenv("INSTANTLY_API_KEY", ""),
            # Social
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
            twitter_api_key=os.getenv("TWITTER_API_KEY", ""),
            twitter_access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
            linkedin_client_id=os.getenv("LINKEDIN_CLIENT_ID", ""),
            linkedin_client_secret=os.getenv("LINKEDIN_CLIENT_SECRET", ""),
            linkedin_ad_token=os.getenv("LINKEDIN_AD_TOKEN", ""),
            instagram_business_id=os.getenv("INSTAGRAM_BUSINESS_ID", ""),
            buffer_api_key=os.getenv("BUFFER_API_KEY", ""),
            producthunt_token=os.getenv("PRODUCTHUNT_TOKEN", ""),
            # SEO & Content
            dataforseo_login=os.getenv("DATAFORSEO_LOGIN", ""),
            dataforseo_password=os.getenv("DATAFORSEO_PASSWORD", ""),
            semrush_api_key=os.getenv("SEMRUSH_API_KEY", ""),
            replicate_api_key=os.getenv("REPLICATE_API_KEY", ""),
            fal_api_key=os.getenv("FAL_API_KEY", ""),
            openai_image_key=os.getenv("OPENAI_IMAGE_KEY", ""),
            # CMS
            wordpress_url=os.getenv("WORDPRESS_URL", ""),
            wordpress_user=os.getenv("WORDPRESS_USER", ""),
            wordpress_app_password=os.getenv("WORDPRESS_APP_PASSWORD", ""),
            ghost_url=os.getenv("GHOST_URL", ""),
            ghost_admin_key=os.getenv("GHOST_ADMIN_KEY", ""),
            webflow_api_key=os.getenv("WEBFLOW_API_KEY", ""),
            webflow_blog_collection_id=os.getenv("WEBFLOW_BLOG_COLLECTION_ID", ""),
            # Plagiarism
            copyscape_user=os.getenv("COPYSCAPE_USER", ""),
            copyscape_api_key=os.getenv("COPYSCAPE_API_KEY", ""),
            # Ads
            meta_access_token=os.getenv("META_ACCESS_TOKEN", ""),
            meta_pixel_id=os.getenv("META_PIXEL_ID", ""),
            google_ads_developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
            google_analytics_id=os.getenv("GOOGLE_ANALYTICS_ID", ""),
            # Deployment & DNS
            vercel_token=os.getenv("VERCEL_TOKEN", ""),
            cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN", ""),
            cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
            cloudflare_r2_access_key=os.getenv("CLOUDFLARE_R2_ACCESS_KEY", ""),
            cloudflare_r2_secret_key=os.getenv("CLOUDFLARE_R2_SECRET_KEY", ""),
            cloudflare_r2_bucket=os.getenv("CLOUDFLARE_R2_BUCKET", ""),
            namecheap_api_user=os.getenv("NAMECHEAP_API_USER", ""),
            namecheap_api_key=os.getenv("NAMECHEAP_API_KEY", ""),
            namecheap_client_ip=os.getenv("NAMECHEAP_CLIENT_IP", ""),
            # Analytics & Monitoring
            plausible_api_key=os.getenv("PLAUSIBLE_API_KEY", ""),
            google_analytics_api_key=os.getenv("GOOGLE_ANALYTICS_API_KEY", ""),
            google_search_console_key=os.getenv("GOOGLE_SEARCH_CONSOLE_KEY", ""),
            google_psi_api_key=os.getenv("GOOGLE_PSI_API_KEY", ""),
            betteruptime_api_key=os.getenv("BETTERUPTIME_API_KEY", ""),
            uptimerobot_api_key=os.getenv("UPTIMEROBOT_API_KEY", ""),
            browserless_api_key=os.getenv("BROWSERLESS_API_KEY", ""),
            screenshotone_api_key=os.getenv("SCREENSHOTONE_API_KEY", ""),
            # CRM & Calendar
            hubspot_api_key=os.getenv("HUBSPOT_API_KEY", ""),
            calcom_api_key=os.getenv("CALCOM_API_KEY", ""),
            # Legal
            docusign_api_key=os.getenv("DOCUSIGN_API_KEY", ""),
            pandadoc_api_key=os.getenv("PANDADOC_API_KEY", ""),
            # Surveys
            typeform_api_key=os.getenv("TYPEFORM_API_KEY", ""),
            # Research
            similarweb_api_key=os.getenv("SIMILARWEB_API_KEY", ""),
            builtwith_api_key=os.getenv("BUILTWITH_API_KEY", ""),
            # Newsletter ESPs
            convertkit_api_key=os.getenv("CONVERTKIT_API_KEY", ""),
            mailchimp_api_key=os.getenv("MAILCHIMP_API_KEY", ""),
            beehiiv_api_key=os.getenv("BEEHIIV_API_KEY", ""),
            beehiiv_publication_id=os.getenv("BEEHIIV_PUBLICATION_ID", ""),
            # Messaging
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_owner_chat_id=os.getenv("TELEGRAM_OWNER_CHAT_ID", ""),
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            owner_email=os.getenv("OWNER_EMAIL", ""),
            # Business Formation
            stripe_atlas_key=os.getenv("STRIPE_ATLAS_KEY", ""),
            firstbase_api_key=os.getenv("FIRSTBASE_API_KEY", ""),
            # Stripe Billing
            stripe_api_key=os.getenv("STRIPE_API_KEY", ""),
            stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            # Referral & Affiliate
            rewardful_api_key=os.getenv("REWARDFUL_API_KEY", ""),
            firstpromoter_api_key=os.getenv("FIRSTPROMOTER_API_KEY", ""),
        )

    @property
    def active_providers(self) -> list:
        return [p for p in self.providers if p.enabled]

    @property
    def primary_provider(self) -> Optional[ProviderConfig]:
        active = self.active_providers
        return active[0] if active else None


settings = Settings.from_env()
