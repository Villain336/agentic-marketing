"""
Omni OS Backend — Persona Gauntlet
Quality gate that validates agent output against simulated buyer personas.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional

from models import Campaign, Tier
from providers import router

logger = logging.getLogger("supervisor.gauntlet")


PERSONAS = [
    {
        "id": "skeptical_cfo",
        "name": "The Skeptical CFO",
        "profile": "CFO at a mid-market company ($5-50M revenue). Data-driven, risk-averse, questions ROI on everything. Has been burned by agencies before. Wants proof, not promises.",
        "buying_style": "Needs 3+ data points before considering. Asks 'what's the downside?' first. Compares to doing nothing.",
    },
    {
        "id": "busy_founder",
        "name": "The Busy Founder",
        "profile": "Series A startup founder. Wearing 5 hats. Has 30 seconds to evaluate anything. Responds to clarity and speed. Hates jargon.",
        "buying_style": "Skims everything. Decides in <60 seconds. 'Will this make me money THIS quarter?' If not immediately clear, moves on.",
    },
    {
        "id": "technical_vp",
        "name": "The Technical VP",
        "profile": "VP of Engineering or Product. Respects competence, allergic to BS. Wants to understand the mechanism, not just the promise.",
        "buying_style": "Reads everything. Checks claims. Googles the company. If anything feels exaggerated, trust is lost permanently.",
    },
    {
        "id": "procurement_gatekeeper",
        "name": "The Procurement Gatekeeper",
        "profile": "Head of Procurement or Ops. Evaluates vendors against a checklist. Cares about compliance, SLAs, and total cost.",
        "buying_style": "Comparison shopper. Creates spreadsheets. Asks for references. Needs to justify the choice to their boss.",
    },
    {
        "id": "enthusiastic_champion",
        "name": "The Internal Champion",
        "profile": "Marketing Director who already wants this. Needs ammunition to sell it internally. Looking for the one slide that convinces their CEO.",
        "buying_style": "Already sold, but needs proof points. 'Give me the stat I can put in front of my boss.' Wants case studies.",
    },
    {
        "id": "burned_buyer",
        "name": "The Burned Buyer",
        "profile": "Has hired 3 agencies in 2 years. All overpromised and underdelivered. Trust is at zero. Looking for someone who admits limitations.",
        "buying_style": "Red flags everywhere. If you promise too much, they're out. Authenticity > polish. Wants realistic timelines.",
    },
    {
        "id": "comparison_shopper",
        "name": "The Comparison Shopper",
        "profile": "Evaluating 4-5 options simultaneously. Has a mental decision matrix. Needs clear differentiation.",
        "buying_style": "Everything is relative. 'Why you and not [competitor]?' Price sensitive but values quality. Wants a clear winner.",
    },
    {
        "id": "enterprise_buyer",
        "name": "The Enterprise Buyer",
        "profile": "Director at Fortune 500. 6-month buying cycles. Needs security review, legal review, procurement review. Values stability.",
        "buying_style": "Risk of choosing wrong vendor > cost of vendor. Needs to know you'll be around in 2 years. References from similar companies required.",
    },
]

# Agents whose output should go through the gauntlet
OUTBOUND_AGENTS = {"outreach", "social", "ads", "newsletter", "content", "sitelaunch"}


class GauntletResult:
    def __init__(self, fit_score: float, persona_reactions: list[dict],
                 top_objections: list[str], recommended_changes: list[str], passed: bool):
        self.fit_score = fit_score
        self.persona_reactions = persona_reactions
        self.top_objections = top_objections
        self.recommended_changes = recommended_changes
        self.passed = passed

    def to_dict(self) -> dict:
        return {
            "fit_score": self.fit_score,
            "passed": self.passed,
            "persona_reactions": self.persona_reactions,
            "top_objections": self.top_objections,
            "recommended_changes": self.recommended_changes,
        }


class PersonaGauntlet:

    async def validate(self, output: str, icp: str, test_type: str = "general",
                       persona_ids: Optional[list[str]] = None) -> GauntletResult:
        """Run output against 3-5 personas matching the ICP."""
        # Select personas
        if persona_ids:
            selected = [p for p in PERSONAS if p["id"] in persona_ids]
        else:
            # Default: use 3 most relevant for B2B
            selected = [PERSONAS[0], PERSONAS[1], PERSONAS[5]]  # Skeptical CFO, Busy Founder, Burned Buyer

        persona_descriptions = "\n".join([
            f"PERSONA {i+1}: {p['name']}\nProfile: {p['profile']}\nBuying style: {p['buying_style']}"
            for i, p in enumerate(selected)
        ])

        system = f"""You are a market validation expert. You simulate real buyer reactions to marketing content.

Target ICP: {icp}
Test type: {test_type}

You have {len(selected)} personas to test against:
{persona_descriptions}

For EACH persona, provide:
1. Name
2. Initial reaction (2-3 sentences — what they think in the first 10 seconds)
3. Sentiment: positive / negative / skeptical
4. Intent: buy / pass / research_more
5. Key objection (the #1 thing that would stop them)
6. Specific fix (exactly what to change to win them over)

After all personas, provide:
- FIT_SCORE: 0-100 (weighted average of how well this resonates)
- TOP_3_OBJECTIONS: The 3 most common concerns across personas
- TOP_3_CHANGES: The 3 highest-impact changes to make

OUTPUT as valid JSON with this structure:
{{
  "personas": [{{ "name": "", "reaction": "", "sentiment": "", "intent": "", "objection": "", "fix": "" }}],
  "fit_score": 0,
  "top_objections": ["", "", ""],
  "recommended_changes": ["", "", ""]
}}"""

        try:
            result = await router.complete(
                messages=[{"role": "user", "content": f"Evaluate this content:\n---\n{output[:4000]}\n---"}],
                system=system, tier=Tier.FAST, max_tokens=2000,
            )

            text = result.get("text", "")
            # Extract JSON from response
            parsed = _extract_json(text)

            if parsed:
                fit_score = parsed.get("fit_score", 50)
                return GauntletResult(
                    fit_score=fit_score,
                    persona_reactions=parsed.get("personas", []),
                    top_objections=parsed.get("top_objections", []),
                    recommended_changes=parsed.get("recommended_changes", []),
                    passed=fit_score >= 40,
                )

            # Fallback: couldn't parse JSON — mark as needing review
            logger.warning("Gauntlet: could not parse LLM response — failing closed")
            return GauntletResult(
                fit_score=35,
                persona_reactions=[{"name": "Parse Error", "reaction": "Could not evaluate"}],
                top_objections=["Gauntlet could not evaluate output — manual review needed"],
                recommended_changes=["Resubmit for evaluation"],
                passed=False,
            )

        except Exception as e:
            logger.error(f"Gauntlet validation failed: {e}")
            return GauntletResult(
                fit_score=35, persona_reactions=[], top_objections=["Gauntlet evaluation unavailable"],
                recommended_changes=[], passed=False,  # Fail closed — require manual review
            )

    async def gate_check(self, agent_id: str, output: str, campaign: Campaign) -> GauntletResult:
        """Quality gate check — blocks low-quality output from going live."""
        if agent_id not in OUTBOUND_AGENTS:
            return GauntletResult(fit_score=100, persona_reactions=[], top_objections=[],
                                  recommended_changes=[], passed=True)

        icp = campaign.memory.business.icp
        result = await self.validate(output, icp, test_type=agent_id)

        if result.fit_score >= 60:
            logger.info(f"Gauntlet PASS for {agent_id}: score={result.fit_score}")
        elif result.fit_score >= 40:
            logger.warning(f"Gauntlet WARN for {agent_id}: score={result.fit_score}")
        else:
            logger.warning(f"Gauntlet FAIL for {agent_id}: score={result.fit_score} — agent should rewrite")

        return result


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding JSON block
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding raw JSON object
    brace_start = text.find('{')
    if brace_start >= 0:
        depth = 0
        for i, c in enumerate(text[brace_start:], brace_start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i+1])
                    except json.JSONDecodeError:
                        break

    return None


gauntlet = PersonaGauntlet()
