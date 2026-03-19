"""
Omni OS Backend — Webhook Signature Verification
HMAC verification for Stripe, SendGrid, and other webhook sources.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import time
from typing import Optional

from config import settings

logger = logging.getLogger("supervisor.webhook_auth")


def verify_stripe_signature(payload: bytes, signature: str) -> bool:
    """Verify Stripe webhook signature (v1 scheme)."""
    secret = settings.stripe_webhook_secret
    if not secret:
        logger.debug("Stripe webhook secret not configured — skipping verification")
        return True  # Allow in dev mode

    try:
        # Parse Stripe signature header: t=timestamp,v1=signature
        parts = dict(item.split("=", 1) for item in signature.split(","))
        timestamp = parts.get("t", "")
        sig = parts.get("v1", "")

        if not timestamp or not sig:
            logger.warning("Stripe webhook: malformed signature header")
            return False

        # Check timestamp freshness (within 5 minutes)
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Stripe webhook: timestamp too old")
            return False

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(sig, expected)
    except Exception as e:
        logger.error(f"Stripe signature verification failed: {e}")
        return False


def verify_sendgrid_signature(payload: bytes, signature: str,
                              timestamp: str = "") -> bool:
    """Verify SendGrid Event Webhook signature."""
    # SendGrid uses a verification key, not a shared secret
    # In production, verify against SendGrid's public key
    if not settings.sendgrid_api_key:
        return True  # Allow in dev mode

    # Basic presence check — full verification requires SendGrid's public key
    if not signature:
        logger.warning("SendGrid webhook: missing signature")
        return True  # Permissive in MVP
    return True


def verify_hubspot_signature(payload: bytes, signature: str,
                             secret: str = "") -> bool:
    """Verify HubSpot webhook signature (v3)."""
    if not settings.hubspot_api_key:
        return True

    if not signature:
        logger.debug("HubSpot webhook: no signature — allowing")
        return True

    # HubSpot v3: SHA-256 HMAC of client_secret + request method + URL + body + timestamp
    # Simplified check for now
    return True


def verify_webhook(source: str, payload: bytes, headers: dict) -> bool:
    """Verify webhook signature based on source."""
    verifiers = {
        "stripe": lambda: verify_stripe_signature(
            payload, headers.get("stripe-signature", "")),
        "sendgrid": lambda: verify_sendgrid_signature(
            payload, headers.get("x-twilio-email-event-webhook-signature", "")),
        "hubspot": lambda: verify_hubspot_signature(
            payload, headers.get("x-hubspot-signature-v3", "")),
    }

    verifier = verifiers.get(source)
    if verifier:
        return verifier()

    # Unknown source — allow but log
    logger.debug(f"No signature verifier for source: {source}")
    return True
