"""
Omni OS Backend — PII Stripping / Privacy Router
Scrubs personally identifiable information before sending to cloud LLMs.
Competes with NemoClaw's enterprise privacy router.
"""
from __future__ import annotations
import re
import hashlib
import logging
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.privacy")


# ═══════════════════════════════════════════════════════════════════════════════
# PII PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

PII_PATTERNS = {
    "email": {
        "pattern": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "placeholder": "[EMAIL_REDACTED_{n}]",
        "severity": "high",
    },
    "phone_us": {
        "pattern": r'\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b',
        "placeholder": "[PHONE_REDACTED_{n}]",
        "severity": "high",
    },
    "phone_intl": {
        "pattern": r'\+\d{1,3}[-.\s]?\d{1,14}(?:[-.\s]?\d{1,13})?',
        "placeholder": "[PHONE_REDACTED_{n}]",
        "severity": "high",
    },
    "ssn": {
        "pattern": r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',
        "placeholder": "[SSN_REDACTED]",
        "severity": "critical",
    },
    "credit_card": {
        "pattern": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "placeholder": "[CC_REDACTED]",
        "severity": "critical",
    },
    "ip_address": {
        "pattern": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        "placeholder": "[IP_REDACTED_{n}]",
        "severity": "medium",
    },
    "street_address": {
        "pattern": r'\b\d{1,5}\s[\w\s]{1,40}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct|Way|Place|Pl)\b',
        "placeholder": "[ADDRESS_REDACTED_{n}]",
        "severity": "high",
    },
    "date_of_birth": {
        "pattern": r'\b(?:DOB|date of birth|born|birthday)[:\s]*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
        "placeholder": "[DOB_REDACTED]",
        "severity": "high",
    },
    "api_key": {
        "pattern": r'\b(?:sk|pk|api|key|token|secret|password)[_-]?[A-Za-z0-9]{16,}\b',
        "placeholder": "[API_KEY_REDACTED]",
        "severity": "critical",
    },
    "aws_key": {
        "pattern": r'\bAKIA[0-9A-Z]{16}\b',
        "placeholder": "[AWS_KEY_REDACTED]",
        "severity": "critical",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class PIIDetection(BaseModel):
    """A single PII detection."""
    type: str                    # email, phone, ssn, etc.
    original: str               # The original text matched
    placeholder: str             # The replacement placeholder
    severity: str                # critical, high, medium, low
    position: tuple[int, int] = (0, 0)


class ScrubResult(BaseModel):
    """Result of PII scrubbing."""
    original_text: str = ""
    scrubbed_text: str = ""
    detections: list[PIIDetection] = []
    pii_count: int = 0
    has_critical: bool = False
    scrub_time_ms: float = 0


class PrivacyConfig(BaseModel):
    """Privacy router configuration."""
    enabled: bool = True
    scrub_inbound: bool = True       # Scrub before sending to cloud LLM
    scrub_outbound: bool = False     # Scrub LLM responses (for logging)
    block_critical: bool = True      # Block requests with critical PII (SSN, CC)
    allowed_pii_types: list[str] = []  # PII types to allow through (e.g., ["email"] for outreach agent)
    log_detections: bool = True
    custom_patterns: dict[str, dict] = {}  # Additional custom patterns


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVACY ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

class PrivacyRouter:
    """
    Scrubs PII from text before it reaches cloud LLMs.
    Maintains a reversible mapping so PII can be restored in responses.
    """

    def __init__(self):
        self._config = PrivacyConfig()
        self._session_maps: dict[str, dict[str, str]] = {}  # session_id -> {placeholder: original}
        self._stats = {"total_scrubbed": 0, "total_detections": 0, "blocked": 0}
        self._agent_overrides: dict[str, list[str]] = {}  # agent_id -> allowed PII types

    def configure(self, config: PrivacyConfig):
        self._config = config

    def set_agent_pii_allowlist(self, agent_id: str, allowed_types: list[str]):
        """
        Allow specific PII types for certain agents.
        e.g., Outreach agent needs emails, Ads agent needs none.
        """
        self._agent_overrides[agent_id] = allowed_types
        logger.info(f"PII allowlist for {agent_id}: {allowed_types}")

    def scrub(self, text: str, session_id: str = "default",
              agent_id: str = "") -> ScrubResult:
        """
        Scrub PII from text. Returns scrubbed text and detection details.
        Maintains a session map for later restoration.
        """
        import time
        start = time.time()

        if not self._config.enabled:
            return ScrubResult(original_text=text, scrubbed_text=text)

        if session_id not in self._session_maps:
            self._session_maps[session_id] = {}

        # Determine which PII types to allow
        allowed = set(self._config.allowed_pii_types)
        if agent_id and agent_id in self._agent_overrides:
            allowed = allowed | set(self._agent_overrides[agent_id])

        detections: list[PIIDetection] = []
        scrubbed = text
        counter = 0

        # Combine built-in and custom patterns
        all_patterns = {**PII_PATTERNS, **self._config.custom_patterns}

        for pii_type, config in all_patterns.items():
            if pii_type in allowed:
                continue

            pattern = config["pattern"]
            severity = config.get("severity", "medium")

            for match in re.finditer(pattern, scrubbed, re.IGNORECASE):
                counter += 1
                original = match.group()
                placeholder = config["placeholder"].format(n=counter)

                # Store mapping for restoration
                self._session_maps[session_id][placeholder] = original

                detection = PIIDetection(
                    type=pii_type, original=original,
                    placeholder=placeholder, severity=severity,
                    position=(match.start(), match.end()),
                )
                detections.append(detection)

        # Apply replacements (reverse order to preserve positions)
        for det in sorted(detections, key=lambda d: d.position[0], reverse=True):
            scrubbed = scrubbed[:det.position[0]] + det.placeholder + scrubbed[det.position[1]:]

        elapsed = (time.time() - start) * 1000
        has_critical = any(d.severity == "critical" for d in detections)

        self._stats["total_scrubbed"] += 1
        self._stats["total_detections"] += len(detections)
        if has_critical and self._config.block_critical:
            self._stats["blocked"] += 1

        result = ScrubResult(
            original_text=text, scrubbed_text=scrubbed,
            detections=detections, pii_count=len(detections),
            has_critical=has_critical, scrub_time_ms=elapsed,
        )

        if detections and self._config.log_detections:
            types = [d.type for d in detections]
            logger.info(f"PII scrubbed: {len(detections)} detections ({', '.join(set(types))})")

        return result

    def restore(self, text: str, session_id: str = "default") -> str:
        """Restore PII placeholders back to original values."""
        mapping = self._session_maps.get(session_id, {})
        restored = text
        for placeholder, original in mapping.items():
            restored = restored.replace(placeholder, original)
        return restored

    def scrub_messages(self, messages: list[dict], session_id: str = "default",
                       agent_id: str = "") -> list[dict]:
        """Scrub PII from a full message list (for LLM calls)."""
        scrubbed_msgs = []
        for msg in messages:
            scrubbed_msg = msg.copy()
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                result = self.scrub(content, session_id, agent_id)
                scrubbed_msg["content"] = result.scrubbed_text
            elif isinstance(content, list):
                scrubbed_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        result = self.scrub(block.get("text", ""), session_id, agent_id)
                        scrubbed_blocks.append({**block, "text": result.scrubbed_text})
                    else:
                        scrubbed_blocks.append(block)
                scrubbed_msg["content"] = scrubbed_blocks
            scrubbed_msgs.append(scrubbed_msg)
        return scrubbed_msgs

    def restore_response(self, response_text: str, session_id: str = "default") -> str:
        """Restore PII in LLM response."""
        return self.restore(response_text, session_id)

    def should_block(self, scrub_result: ScrubResult) -> bool:
        """Check if a request should be blocked due to critical PII."""
        return self._config.block_critical and scrub_result.has_critical

    def clear_session(self, session_id: str):
        """Clear PII mapping for a session."""
        self._session_maps.pop(session_id, None)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "config": self._config.model_dump(),
            "active_sessions": len(self._session_maps),
            "agent_overrides": self._agent_overrides,
        }

    def audit_log(self, session_id: str = None) -> list[dict]:
        """Get audit log of PII detections (without revealing the PII itself)."""
        if session_id:
            mapping = self._session_maps.get(session_id, {})
            return [
                {"placeholder": p, "type": p.split("_")[0].strip("["),
                 "session": session_id}
                for p in mapping.keys()
            ]
        return [
            {"session": sid, "pii_count": len(mapping)}
            for sid, mapping in self._session_maps.items()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

privacy_router = PrivacyRouter()
