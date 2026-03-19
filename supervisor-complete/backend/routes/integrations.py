"""Integration key management -- masked display, validation, never raw exposure."""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from auth import get_user_id, require_role

logger = logging.getLogger("supervisor.api.integrations")

router = APIRouter(prefix="/integrations", tags=["Integrations"])


def _mask_key(key: str) -> str:
    """Mask an API key, showing only first 4 and last 4 characters."""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "*" * (len(key) - 2)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# All integration key categories with their settings field names
INTEGRATION_CATEGORIES = {
    "llm": {
        "label": "LLM Providers",
        "keys": [
            {"id": "OPENROUTER_API_KEY", "field": None, "label": "OpenRouter"},
            {"id": "ANTHROPIC_API_KEY", "field": None, "label": "Anthropic"},
            {"id": "OPENAI_API_KEY", "field": None, "label": "OpenAI"},
            {"id": "GOOGLE_API_KEY", "field": None, "label": "Google AI"},
        ],
    },
    "email": {
        "label": "Email & Outreach",
        "keys": [
            {"id": "sendgrid_api_key", "field": "sendgrid_api_key", "label": "SendGrid"},
            {"id": "instantly_api_key", "field": "instantly_api_key", "label": "Instantly"},
        ],
    },
    "prospecting": {
        "label": "Prospecting & Enrichment",
        "keys": [
            {"id": "apollo_api_key", "field": "apollo_api_key", "label": "Apollo.io"},
            {"id": "hunter_api_key", "field": "hunter_api_key", "label": "Hunter.io"},
            {"id": "clearbit_api_key", "field": "clearbit_api_key", "label": "Clearbit"},
            {"id": "serper_api_key", "field": "serper_api_key", "label": "Serper"},
        ],
    },
    "social": {
        "label": "Social Media",
        "keys": [
            {"id": "twitter_bearer_token", "field": "twitter_bearer_token", "label": "Twitter/X"},
            {"id": "linkedin_client_id", "field": "linkedin_client_id", "label": "LinkedIn"},
            {"id": "buffer_api_key", "field": "buffer_api_key", "label": "Buffer"},
        ],
    },
    "crm": {
        "label": "CRM & Sales",
        "keys": [
            {"id": "hubspot_api_key", "field": "hubspot_api_key", "label": "HubSpot"},
            {"id": "calcom_api_key", "field": "calcom_api_key", "label": "Cal.com"},
        ],
    },
    "payments": {
        "label": "Payments & Billing",
        "keys": [
            {"id": "stripe_api_key", "field": "stripe_api_key", "label": "Stripe"},
        ],
    },
    "deployment": {
        "label": "Deployment & DNS",
        "keys": [
            {"id": "vercel_token", "field": "vercel_token", "label": "Vercel"},
            {"id": "cloudflare_api_token", "field": "cloudflare_api_token", "label": "Cloudflare"},
        ],
    },
    "messaging": {
        "label": "Messaging",
        "keys": [
            {"id": "telegram_bot_token", "field": "telegram_bot_token", "label": "Telegram"},
            {"id": "slack_bot_token", "field": "slack_bot_token", "label": "Slack"},
            {"id": "whatsapp_access_token", "field": "whatsapp_access_token", "label": "WhatsApp"},
        ],
    },
}


@router.get("")
async def list_integrations(request: Request):
    """List all integration keys with masked values -- never exposes raw keys."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    result = {}
    for cat_id, cat in INTEGRATION_CATEGORIES.items():
        keys = []
        for key_def in cat["keys"]:
            field = key_def.get("field")
            raw = getattr(settings, field, "") if field else ""
            # For LLM providers, check the provider configs
            if cat_id == "llm":
                for p in settings.providers:
                    if p.name.lower() in key_def["id"].lower():
                        raw = p.api_key or ""
                        break
            keys.append({
                "id": key_def["id"],
                "label": key_def["label"],
                "configured": bool(raw),
                "masked_value": _mask_key(raw) if raw else "",
            })
        result[cat_id] = {"label": cat["label"], "keys": keys}
    return result


@router.get("/status")
async def integration_health(request: Request):
    """Quick health check -- which integrations are configured vs missing."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    configured = 0
    total = 0
    missing = []

    for cat_id, cat in INTEGRATION_CATEGORIES.items():
        for key_def in cat["keys"]:
            total += 1
            field = key_def.get("field")
            raw = getattr(settings, field, "") if field else ""
            if cat_id == "llm":
                for p in settings.providers:
                    if p.name.lower() in key_def["id"].lower():
                        raw = p.api_key or ""
                        break
            if raw:
                configured += 1
            else:
                missing.append({"id": key_def["id"], "label": key_def["label"],
                                "category": cat["label"]})

    return {
        "configured": configured,
        "total": total,
        "missing": missing,
        "completion_pct": round(configured / max(total, 1) * 100, 1),
    }
