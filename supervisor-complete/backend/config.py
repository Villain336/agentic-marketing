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
    strong_model: str = ""
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
    cors_origins: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:8000",
    ])

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
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    youtube_api_key: str = ""
    tiktok_business_api_key: str = ""

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
    harvey_api_key: str = ""

    # Design
    figma_api_key: str = ""
    figma_team_id: str = ""

    # Surveys
    typeform_api_key: str = ""

    # Economic Intelligence
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    polygon_api_key: str = ""
    newsapi_key: str = ""

    # Knowledge & Vectors
    pinecone_api_key: str = ""
    pinecone_environment: str = ""

    # Code Sandbox
    e2b_api_key: str = ""

    # Helpdesk
    zendesk_subdomain: str = ""
    zendesk_api_key: str = ""
    zendesk_email: str = ""

    # Project Management
    linear_api_key: str = ""

    # Security Scanning
    snyk_api_key: str = ""

    # Manufacturing
    octoprint_url: str = ""
    octoprint_api_key: str = ""
    xometry_api_key: str = ""

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

    # WhatsApp Business
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Business Formation
    stripe_atlas_key: str = ""
    firstbase_api_key: str = ""

    # Stripe Billing
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    # Referral & Affiliate
    rewardful_api_key: str = ""
    firstpromoter_api_key: str = ""

    # AWS Infrastructure
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_account_id: str = ""
    aws_bedrock_region: str = "us-east-1"
    aws_sagemaker_role_arn: str = ""
    aws_eks_cluster_name: str = ""
    aws_iot_endpoint: str = ""
    aws_s3_bucket: str = "supervisor-artifacts"

    # NVIDIA Infrastructure
    nvidia_api_key: str = ""
    nvidia_ngc_api_key: str = ""
    triton_server_url: str = "http://localhost:8001"
    omniverse_server_url: str = ""
    isaac_sim_url: str = ""
    metropolis_url: str = ""
    nvidia_gpu_cluster_endpoint: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        providers = []

        # OpenRouter — unified gateway, priority 0 (primary)
        # One key gives access to all models: Anthropic, OpenAI, Google, Mistral, etc.
        providers.append(ProviderConfig(
            name="openrouter",
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api",
            strong_model=os.getenv("OPENROUTER_STRONG_MODEL", "anthropic/claude-sonnet-4-20250514"),
            default_model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-20250514"),
            fast_model=os.getenv("OPENROUTER_FAST_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            priority=0,
            timeout=int(os.getenv("OPENROUTER_TIMEOUT", "120")),
        ))

        # Direct provider fallbacks (if user has their own keys)
        providers.append(ProviderConfig(
            name="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url="https://api.anthropic.com",
            strong_model=os.getenv("ANTHROPIC_STRONG_MODEL", "claude-sonnet-4-20250514"),
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

        # AWS Bedrock — managed LLM endpoints, priority 1.5
        providers.append(ProviderConfig(
            name="bedrock",
            api_key=os.getenv("AWS_ACCESS_KEY_ID", ""),  # Uses AWS creds
            base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
            strong_model=os.getenv("BEDROCK_STRONG_MODEL", "claude-sonnet"),
            default_model=os.getenv("BEDROCK_MODEL", "claude-sonnet"),
            fast_model=os.getenv("BEDROCK_FAST_MODEL", "claude-haiku"),
            priority=15,  # Between anthropic (1) and openai (2) — sorted numerically
            timeout=int(os.getenv("BEDROCK_TIMEOUT", "120")),
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

        # CORS origins from env (comma-separated), defaults to localhost
        cors_raw = os.getenv("CORS_ORIGINS", "")
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()] if cors_raw else [
            "http://localhost:3000",
            "http://localhost:8000",
        ]

        return cls(
            cors_origins=cors_origins,
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
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID", ""),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            tiktok_business_api_key=os.getenv("TIKTOK_BUSINESS_API_KEY", ""),
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
            # Legal & Documents
            docusign_api_key=os.getenv("DOCUSIGN_API_KEY", ""),
            pandadoc_api_key=os.getenv("PANDADOC_API_KEY", ""),
            harvey_api_key=os.getenv("HARVEY_API_KEY", ""),
            # Design
            figma_api_key=os.getenv("FIGMA_API_KEY", ""),
            figma_team_id=os.getenv("FIGMA_TEAM_ID", ""),
            # Surveys
            typeform_api_key=os.getenv("TYPEFORM_API_KEY", ""),
            # Economic Intelligence
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
            fred_api_key=os.getenv("FRED_API_KEY", ""),
            polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
            newsapi_key=os.getenv("NEWSAPI_KEY", ""),
            # Knowledge & Vectors
            pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
            pinecone_environment=os.getenv("PINECONE_ENVIRONMENT", ""),
            # Code Sandbox
            e2b_api_key=os.getenv("E2B_API_KEY", ""),
            # Helpdesk
            zendesk_subdomain=os.getenv("ZENDESK_SUBDOMAIN", ""),
            zendesk_api_key=os.getenv("ZENDESK_API_KEY", ""),
            zendesk_email=os.getenv("ZENDESK_EMAIL", ""),
            # Project Management
            linear_api_key=os.getenv("LINEAR_API_KEY", ""),
            # Security Scanning
            snyk_api_key=os.getenv("SNYK_API_KEY", ""),
            # Manufacturing
            octoprint_url=os.getenv("OCTOPRINT_URL", ""),
            octoprint_api_key=os.getenv("OCTOPRINT_API_KEY", ""),
            xometry_api_key=os.getenv("XOMETRY_API_KEY", ""),
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
            # WhatsApp Business
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", ""),
            whatsapp_app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
            # Business Formation
            stripe_atlas_key=os.getenv("STRIPE_ATLAS_KEY", ""),
            firstbase_api_key=os.getenv("FIRSTBASE_API_KEY", ""),
            # Stripe Billing
            stripe_api_key=os.getenv("STRIPE_API_KEY", ""),
            stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            # Referral & Affiliate
            rewardful_api_key=os.getenv("REWARDFUL_API_KEY", ""),
            firstpromoter_api_key=os.getenv("FIRSTPROMOTER_API_KEY", ""),
            # AWS Infrastructure
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_account_id=os.getenv("AWS_ACCOUNT_ID", ""),
            aws_bedrock_region=os.getenv("AWS_BEDROCK_REGION", "us-east-1"),
            aws_sagemaker_role_arn=os.getenv("AWS_SAGEMAKER_ROLE_ARN", ""),
            aws_eks_cluster_name=os.getenv("AWS_EKS_CLUSTER_NAME", ""),
            aws_iot_endpoint=os.getenv("AWS_IOT_ENDPOINT", ""),
            aws_s3_bucket=os.getenv("AWS_S3_BUCKET", "supervisor-artifacts"),
            # NVIDIA Infrastructure
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
            nvidia_ngc_api_key=os.getenv("NVIDIA_NGC_API_KEY", ""),
            triton_server_url=os.getenv("TRITON_SERVER_URL", "http://localhost:8001"),
            omniverse_server_url=os.getenv("OMNIVERSE_SERVER_URL", ""),
            isaac_sim_url=os.getenv("ISAAC_SIM_URL", ""),
            metropolis_url=os.getenv("METROPOLIS_URL", ""),
            nvidia_gpu_cluster_endpoint=os.getenv("NVIDIA_GPU_CLUSTER_ENDPOINT", ""),
        )

    @property
    def active_providers(self) -> list:
        return [p for p in self.providers if p.enabled]

    @property
    def primary_provider(self) -> Optional[ProviderConfig]:
        active = self.active_providers
        return active[0] if active else None


settings = Settings.from_env()
