"""
Omni OS Backend — Multi-Modal Intelligence Extensions

Extends agents beyond text-only thinking:
- Visual verification of deployed sites via computer use
- Image/video creative generation for ads and social
- Audio processing for voice receptionist
- Document analysis for legal and compliance
- Design system generation for brand consistency
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("omnios.multimodal")


# ═══════════════════════════════════════════════════════════════════════════════
# MODALITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    SCREENSHOT = "screenshot"
    DESIGN = "design"


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL VERIFICATION — Screenshot + Vision Analysis of Deployed Sites
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualAuditResult:
    """Result of a visual audit of a deployed site/page."""
    url: str = ""
    screenshot_b64: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    mobile_friendly: bool = True
    load_time_ms: int = 0
    above_fold_cta_visible: bool = False
    social_proof_visible: bool = False
    brand_consistent: bool = True
    audited_at: str = ""


class VisualVerifier:
    """
    Uses computer_use vision capabilities to audit deployed sites.
    Checks: CTA visibility, social proof, brand consistency, mobile
    responsiveness, page speed, and content-ad alignment.
    """

    # Visual audit checklist — what we verify on every deployed page
    AUDIT_CHECKS = [
        {
            "name": "above_fold_cta",
            "prompt": "Is there a clear call-to-action button visible without scrolling?",
            "weight": 0.25,
        },
        {
            "name": "social_proof",
            "prompt": "Is there social proof (testimonials, logos, stats) visible above the fold?",
            "weight": 0.20,
        },
        {
            "name": "value_prop_clarity",
            "prompt": "Can you understand what this product/service does within 5 seconds of looking at the page?",
            "weight": 0.25,
        },
        {
            "name": "visual_hierarchy",
            "prompt": "Is there a clear visual hierarchy guiding the eye from headline to CTA?",
            "weight": 0.15,
        },
        {
            "name": "mobile_responsive",
            "prompt": "Does the layout appear mobile-friendly (no horizontal scroll, readable text)?",
            "weight": 0.15,
        },
    ]

    async def audit_url(self, url: str, brand_guidelines: dict | None = None) -> VisualAuditResult:
        """
        Take a screenshot of the URL and run visual analysis.
        Uses the computer_use BrowserSession for screenshot capture
        and the LLM vision model for analysis.
        """
        result = VisualAuditResult(url=url)

        try:
            from computer_use import BrowserSession
        except ImportError:
            logger.warning("computer_use module not available — skipping screenshot capture")
            result.issues.append("computer_use module not installed — visual audit unavailable")
            return result

        try:
            session = BrowserSession(session_id=f"audit_{int(time.time())}")
            await session.start()

            # Navigate and capture
            await session.navigate(url)
            await asyncio.sleep(2)  # Wait for page load
            screenshot = await session.screenshot()
            result.screenshot_b64 = screenshot
            result.load_time_ms = int(session.last_load_time_ms)

            await session.close()
        except Exception as e:
            logger.warning(f"Screenshot capture failed for {url}: {e}")
            result.issues.append(f"Could not capture screenshot: {e}")
            return result

        # Run vision analysis on the screenshot
        try:
            from providers import router
            vision_prompt = self._build_vision_prompt(brand_guidelines)

            response = ""
            async for chunk in router.complete_stream(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64",
                         "media_type": "image/png", "data": screenshot}},
                        {"type": "text", "text": vision_prompt},
                    ],
                }],
                system="You are a UX/conversion expert auditing a landing page.",
                max_tokens=1500,
            ):
                if chunk["type"] == "text":
                    response += chunk["text"]

            result = self._parse_vision_response(result, response)
        except Exception as e:
            logger.warning(f"Vision analysis failed for {url}: {e}")
            result.issues.append(f"Vision analysis unavailable: {e}")

        result.audited_at = datetime.now(timezone.utc).isoformat()
        return result

    def _build_vision_prompt(self, brand_guidelines: dict | None) -> str:
        lines = [
            "Analyze this landing page screenshot and evaluate:",
            "",
        ]
        for check in self.AUDIT_CHECKS:
            lines.append(f"- {check['name']}: {check['prompt']}")

        lines.extend([
            "",
            "For each check, score 0-100 and explain briefly.",
            "Also list any UX issues and improvement suggestions.",
            "Format as JSON with keys: scores (dict), issues (list), suggestions (list),",
            "above_fold_cta_visible (bool), social_proof_visible (bool).",
        ])

        if brand_guidelines:
            lines.append(f"\nBrand guidelines to check against: {brand_guidelines}")

        return "\n".join(lines)

    def _parse_vision_response(self, result: VisualAuditResult, response: str) -> VisualAuditResult:
        """Parse the vision model's response into structured audit data."""
        import json
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                result.scores = data.get("scores", {})
                result.issues = data.get("issues", [])
                result.suggestions = data.get("suggestions", [])
                result.above_fold_cta_visible = data.get("above_fold_cta_visible", False)
                result.social_proof_visible = data.get("social_proof_visible", False)
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails, extract what we can from text
            result.issues.append("Could not parse structured audit response")
            if "cta" in response.lower() and "not visible" in response.lower():
                result.above_fold_cta_visible = False
            if "social proof" in response.lower() and "missing" in response.lower():
                result.social_proof_visible = False

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# CREATIVE GENERATION — Images, Video Scripts, Ad Creatives
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CreativeAsset:
    """A generated creative asset."""
    asset_id: str = ""
    asset_type: Modality = Modality.IMAGE
    prompt_used: str = ""
    url: str = ""                # URL if hosted
    b64_data: str = ""           # base64 if in-memory
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""           # which agent requested this
    campaign_id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.asset_id:
            import uuid
            self.asset_id = f"asset_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class CreativeEngine:
    """
    Generates multi-modal creative assets for agents.
    Routes to appropriate generation APIs based on modality.
    """

    def __init__(self):
        self._assets: dict[str, CreativeAsset] = {}
        self._generation_queue: asyncio.Queue | None = None

    async def generate_ad_creative(
        self,
        headline: str,
        body_text: str,
        cta: str,
        brand_colors: list[str] | None = None,
        style: str = "professional",
        platform: str = "meta",       # meta, google, linkedin
        agent_id: str = "",
        campaign_id: str = "",
    ) -> CreativeAsset:
        """Generate an ad creative image."""
        prompt = (
            f"Create a {platform} ad creative. Style: {style}. "
            f"Headline: '{headline}'. Body: '{body_text}'. CTA: '{cta}'. "
        )
        if brand_colors:
            prompt += f"Brand colors: {', '.join(brand_colors)}. "
        prompt += "Clean, professional design. No stock photo feel."

        asset = CreativeAsset(
            asset_type=Modality.IMAGE,
            prompt_used=prompt,
            agent_id=agent_id,
            campaign_id=campaign_id,
            metadata={
                "platform": platform, "headline": headline,
                "cta": cta, "style": style,
            },
        )

        # Try real image generation
        try:
            from tools.content import _generate_image_impl
            result = await _generate_image_impl(prompt)
            if result.get("url"):
                asset.url = result["url"]
            elif result.get("b64"):
                asset.b64_data = result["b64"]
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")
            asset.metadata["generation_status"] = "pending"
            asset.metadata["error"] = str(e)

        self._assets[asset.asset_id] = asset
        return asset

    async def generate_social_visual(
        self,
        post_text: str,
        platform: str = "linkedin",
        visual_style: str = "infographic",
        agent_id: str = "",
        campaign_id: str = "",
    ) -> CreativeAsset:
        """Generate a visual for a social media post."""
        prompt = (
            f"Create a {visual_style} for {platform}. "
            f"Content theme: '{post_text[:200]}'. "
            f"Optimized for {platform} feed dimensions. "
            f"Clean, shareable design with strong visual hierarchy."
        )

        asset = CreativeAsset(
            asset_type=Modality.IMAGE,
            prompt_used=prompt,
            agent_id=agent_id,
            campaign_id=campaign_id,
            metadata={"platform": platform, "style": visual_style},
        )

        try:
            from tools.content import _generate_image_impl
            result = await _generate_image_impl(prompt)
            if result.get("url"):
                asset.url = result["url"]
        except Exception as e:
            logger.warning(f"Social visual generation failed: {e}")
            asset.metadata["generation_status"] = "pending"

        self._assets[asset.asset_id] = asset
        return asset

    def generate_video_script(
        self,
        topic: str,
        duration_seconds: int = 60,
        platform: str = "youtube_shorts",
        tone: str = "engaging",
    ) -> dict:
        """
        Generate a structured video script with b-roll guidance.
        Returns a script dict, not a video — agents can use this to
        brief a video editor or feed into video generation APIs.
        """
        script = {
            "platform": platform,
            "target_duration": duration_seconds,
            "tone": tone,
            "topic": topic,
            "sections": [],
        }

        if duration_seconds <= 60:
            # Short-form: hook → value → CTA
            script["sections"] = [
                {
                    "timestamp": "0:00-0:03",
                    "type": "hook",
                    "script": f"[HOOK - pattern interrupt about {topic}]",
                    "b_roll": "Quick-cut montage or text overlay",
                    "on_screen_text": "[Key stat or question]",
                },
                {
                    "timestamp": "0:03-0:45",
                    "type": "value",
                    "script": f"[Main content delivering insight about {topic}]",
                    "b_roll": "Screen recordings, demonstrations, or talking head",
                    "on_screen_text": "[Key points as bullet overlays]",
                },
                {
                    "timestamp": "0:45-0:60",
                    "type": "cta",
                    "script": "[Call to action — follow for more, link in bio, etc.]",
                    "b_roll": "Logo + CTA graphic",
                    "on_screen_text": "[CTA text + handle]",
                },
            ]
        else:
            # Long-form: hook → problem → solution → proof → CTA
            mid = duration_seconds // 2
            script["sections"] = [
                {
                    "timestamp": f"0:00-0:15",
                    "type": "hook",
                    "script": f"[Open with surprising fact or question about {topic}]",
                    "b_roll": "Dramatic visual or text overlay",
                },
                {
                    "timestamp": f"0:15-{mid // 60}:{mid % 60:02d}",
                    "type": "problem_solution",
                    "script": f"[Explore the problem and present the solution]",
                    "b_roll": "Before/after, demonstrations, screen recordings",
                },
                {
                    "timestamp": f"{mid // 60}:{mid % 60:02d}-{(duration_seconds - 15) // 60}:{(duration_seconds - 15) % 60:02d}",
                    "type": "proof",
                    "script": "[Show results, case studies, testimonials]",
                    "b_roll": "Data visualizations, customer clips, metrics",
                },
                {
                    "timestamp": f"{(duration_seconds - 15) // 60}:{(duration_seconds - 15) % 60:02d}-{duration_seconds // 60}:{duration_seconds % 60:02d}",
                    "type": "cta",
                    "script": "[Strong call to action]",
                    "b_roll": "End card with links and social handles",
                },
            ]

        return script

    def get_asset(self, asset_id: str) -> Optional[dict]:
        asset = self._assets.get(asset_id)
        return asset.__dict__ if asset else None

    def list_assets(self, campaign_id: str = "", agent_id: str = "") -> list[dict]:
        assets = list(self._assets.values())
        if campaign_id:
            assets = [a for a in assets if a.campaign_id == campaign_id]
        if agent_id:
            assets = [a for a in assets if a.agent_id == agent_id]
        return [
            {
                "asset_id": a.asset_id, "type": a.asset_type.value,
                "url": a.url, "agent_id": a.agent_id,
                "campaign_id": a.campaign_id, "created_at": a.created_at,
                "metadata": a.metadata,
            }
            for a in assets
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS — Legal, Compliance, Contract Review
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentAnalyzer:
    """
    Analyzes documents for legal, compliance, and business intelligence agents.
    Supports: contracts, invoices, financial statements, compliance docs.
    """

    async def analyze_document(
        self,
        content: str,
        doc_type: str = "contract",
        analysis_goals: list[str] | None = None,
    ) -> dict:
        """Analyze a document using LLM with structured extraction."""
        goals = analysis_goals or self._default_goals(doc_type)

        try:
            from providers import router

            prompt = (
                f"Analyze this {doc_type}. Extract the following:\n"
                + "\n".join(f"- {g}" for g in goals)
                + "\n\nReturn structured JSON with keys matching the analysis goals.\n\n"
                f"Document:\n{content[:8000]}"
            )

            response = ""
            async for chunk in router.complete_stream(
                messages=[{"role": "user", "content": prompt}],
                system=f"You are an expert {doc_type} analyst. Extract structured data from documents.",
                max_tokens=2000,
            ):
                if chunk["type"] == "text":
                    response += chunk["text"]

            # Try to parse JSON from response
            import json
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
            return {"raw_analysis": response}

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return {"error": str(e)}

    def _default_goals(self, doc_type: str) -> list[str]:
        goals_map = {
            "contract": [
                "Parties involved", "Key terms and obligations",
                "Payment terms", "Termination clauses",
                "Liability and indemnification", "Renewal terms",
                "Risk flags or unusual clauses",
            ],
            "invoice": [
                "Vendor/supplier", "Total amount", "Line items",
                "Payment terms", "Due date", "Tax details",
            ],
            "financial_statement": [
                "Revenue", "Expenses", "Net income",
                "Key ratios", "YoY changes", "Notable items",
            ],
            "compliance": [
                "Regulatory requirements", "Compliance status",
                "Gaps identified", "Remediation needed",
                "Deadlines", "Risk level",
            ],
        }
        return goals_map.get(doc_type, ["Key information", "Action items", "Risk flags"])


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT MODALITY CAPABILITIES — Which agents can use which modalities
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_MODALITIES: dict[str, list[Modality]] = {
    "ads": [Modality.IMAGE, Modality.VIDEO],
    "social": [Modality.IMAGE, Modality.VIDEO],
    "content": [Modality.IMAGE, Modality.VIDEO, Modality.DOCUMENT],
    "sitelaunch": [Modality.IMAGE, Modality.SCREENSHOT, Modality.DESIGN],
    "fullstack_dev": [Modality.SCREENSHOT, Modality.DESIGN],
    "design": [Modality.IMAGE, Modality.DESIGN],
    "legal": [Modality.DOCUMENT],
    "governance": [Modality.DOCUMENT],
    "finance": [Modality.DOCUMENT],
    "voice_receptionist": [Modality.AUDIO],
    "pr_comms": [Modality.IMAGE, Modality.VIDEO, Modality.DOCUMENT],
    "agent_ops": [Modality.SCREENSHOT],
    "newsletter": [Modality.IMAGE],
}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════════

visual_verifier = VisualVerifier()
creative_engine = CreativeEngine()
document_analyzer = DocumentAnalyzer()
