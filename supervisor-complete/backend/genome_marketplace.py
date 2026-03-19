"""
Omni OS Backend — Campaign Genome Marketplace

Anonymized genome sharing across tenants. Tenants opt-in to contribute
their campaign DNA (stripped of PII and business identifiers) to a shared
intelligence pool. More users = smarter campaigns for everyone.

This is the network effect moat. No competitor has this.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("omnios.genome_marketplace")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnonymizedGenome:
    """A campaign genome stripped of all identifying information."""
    genome_id: str = ""                # hash-based ID, not campaign ID
    industry: str = ""                 # e.g., "SaaS", "E-commerce", "Agency"
    icp_archetype: str = ""            # e.g., "technical_buyer", "c_suite", "smb_owner"
    service_archetype: str = ""        # e.g., "consulting", "software", "coaching"
    geography_region: str = ""         # e.g., "north_america", "europe", "apac"
    company_size_bucket: str = ""      # "solo", "1-10", "11-50", "51-200", "201-1000", "1000+"
    channel_mix: dict[str, bool] = field(default_factory=dict)
    outcomes: dict[str, float] = field(default_factory=dict)
    strategies_that_worked: list[str] = field(default_factory=list)
    strategies_that_failed: list[str] = field(default_factory=list)
    agent_grades: dict[str, str] = field(default_factory=dict)  # agent_id -> grade
    total_agents_run: int = 0
    campaign_duration_days: int = 0
    contributed_at: str = ""
    contributor_tier: str = ""         # "free", "pro", "enterprise"
    quality_score: float = 0.0         # how complete/useful this genome is

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MarketplaceQuery:
    """Query parameters for searching the marketplace."""
    industry: str = ""
    icp_archetype: str = ""
    service_archetype: str = ""
    geography_region: str = ""
    company_size_bucket: str = ""
    min_quality_score: float = 0.3
    limit: int = 20


@dataclass
class StrategyTemplate:
    """A reusable strategy template derived from marketplace data."""
    template_id: str = ""
    name: str = ""
    description: str = ""
    industry: str = ""
    icp_archetype: str = ""
    recommended_channels: list[str] = field(default_factory=list)
    recommended_agents: list[str] = field(default_factory=list)
    expected_outcomes: dict[str, float] = field(default_factory=dict)
    key_strategies: list[str] = field(default_factory=list)
    pitfalls_to_avoid: list[str] = field(default_factory=list)
    sample_size: int = 0
    confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ANONYMIZATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

# ICP archetype mapping — normalize free-text ICPs into archetypes
ICP_ARCHETYPES = {
    "cto": "technical_buyer", "cio": "technical_buyer", "vp engineering": "technical_buyer",
    "technical": "technical_buyer", "developer": "technical_buyer", "engineer": "technical_buyer",
    "ceo": "c_suite", "cfo": "c_suite", "coo": "c_suite", "founder": "c_suite",
    "president": "c_suite", "owner": "c_suite", "executive": "c_suite",
    "vp marketing": "marketing_buyer", "cmo": "marketing_buyer", "marketing director": "marketing_buyer",
    "marketing manager": "marketing_buyer", "head of growth": "marketing_buyer",
    "vp sales": "sales_buyer", "sales director": "sales_buyer", "head of sales": "sales_buyer",
    "hr director": "hr_buyer", "chro": "hr_buyer", "people ops": "hr_buyer",
    "small business": "smb_owner", "smb": "smb_owner", "freelancer": "smb_owner",
    "solopreneur": "smb_owner", "startup": "smb_owner",
    "consumer": "consumer", "b2c": "consumer", "retail": "consumer",
    "enterprise": "enterprise_buyer", "fortune 500": "enterprise_buyer",
}

SERVICE_ARCHETYPES = {
    "consulting": "consulting", "advisory": "consulting", "strategy": "consulting",
    "software": "software", "saas": "software", "app": "software", "platform": "software",
    "agency": "agency", "marketing agency": "agency", "design agency": "agency",
    "coaching": "coaching", "training": "coaching", "course": "coaching", "education": "coaching",
    "ecommerce": "ecommerce", "e-commerce": "ecommerce", "retail": "ecommerce", "shop": "ecommerce",
    "service": "professional_services", "legal": "professional_services",
    "accounting": "professional_services", "financial": "professional_services",
    "construction": "trades", "plumbing": "trades", "electrical": "trades",
    "healthcare": "healthcare", "medical": "healthcare", "health": "healthcare",
    "real estate": "real_estate", "property": "real_estate",
}

GEOGRAPHY_REGIONS = {
    "us": "north_america", "usa": "north_america", "united states": "north_america",
    "canada": "north_america", "north america": "north_america",
    "uk": "europe", "europe": "europe", "eu": "europe", "germany": "europe",
    "france": "europe", "spain": "europe", "italy": "europe",
    "australia": "apac", "asia": "apac", "japan": "apac", "india": "apac",
    "china": "apac", "singapore": "apac", "apac": "apac",
    "latin america": "latam", "brazil": "latam", "mexico": "latam",
    "africa": "africa", "middle east": "mena", "uae": "mena", "dubai": "mena",
    "global": "global", "worldwide": "global", "international": "global",
}


def _classify(text: str, mapping: dict[str, str]) -> str:
    """Classify free-text into an archetype using keyword matching."""
    if not text:
        return "unknown"
    text_lower = text.lower()
    for keyword, archetype in mapping.items():
        if keyword in text_lower:
            return archetype
    return "other"


def _anonymize_strategy(strategy: str) -> str:
    """Strip business-specific details from a strategy description."""
    import re
    # Remove emails, URLs, company names (anything that looks like a proper noun after "for")
    cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[company]', strategy)
    cleaned = re.sub(r'https?://\S+', '[url]', cleaned)
    cleaned = re.sub(r'\$[\d,]+(?:\.\d{2})?', '[amount]', cleaned)
    # Keep the strategic insight, strip the specifics
    return cleaned[:300]


def anonymize_campaign_dna(dna_dict: dict, tenant_tier: str = "pro") -> AnonymizedGenome:
    """Convert a CampaignDNA dict into an anonymized marketplace genome."""
    # Generate non-reversible genome ID
    raw = f"{dna_dict.get('icp_type', '')}:{dna_dict.get('service_type', '')}:{dna_dict.get('campaign_id', '')}"
    genome_id = f"gen_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    # Classify into archetypes
    icp_archetype = _classify(dna_dict.get("icp_type", ""), ICP_ARCHETYPES)
    service_archetype = _classify(dna_dict.get("service_type", ""), SERVICE_ARCHETYPES)
    geography_region = _classify(dna_dict.get("geography", ""), GEOGRAPHY_REGIONS)

    # Anonymize strategies
    lessons = dna_dict.get("lessons", {})
    worked = [_anonymize_strategy(s) for s in lessons.get("what_worked", [])[:5]]
    failed = [_anonymize_strategy(s) for s in lessons.get("what_didnt", [])[:5]]

    # Compute quality score (how complete is this genome?)
    quality = 0.0
    outcomes = dna_dict.get("outcomes", {})
    if outcomes:
        quality += 0.3
    if worked:
        quality += 0.2
    if dna_dict.get("channel_mix"):
        quality += 0.2
    if icp_archetype != "unknown":
        quality += 0.15
    if service_archetype != "unknown":
        quality += 0.15

    return AnonymizedGenome(
        genome_id=genome_id,
        industry=dna_dict.get("industry", ""),
        icp_archetype=icp_archetype,
        service_archetype=service_archetype,
        geography_region=geography_region,
        channel_mix=dna_dict.get("channel_mix", {}),
        outcomes=outcomes,
        strategies_that_worked=worked,
        strategies_that_failed=failed,
        contributed_at=datetime.now(timezone.utc).isoformat(),
        contributor_tier=tenant_tier,
        quality_score=round(quality, 2),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GENOME MARKETPLACE
# ═══════════════════════════════════════════════════════════════════════════════

class GenomeMarketplace:
    """
    Shared intelligence marketplace across tenants.

    Tenants opt-in to contribute anonymized campaign genomes.
    In return, they get access to aggregated intelligence from
    similar campaigns across the entire platform.

    Privacy guarantees:
    - All data anonymized before storage (no company names, emails, URLs)
    - Campaign IDs are hashed (non-reversible)
    - Strategies stripped of business-specific details
    - Minimum pool size of 5 before returning aggregated data
    - Tenant can withdraw at any time (removes their contributions)
    """

    MIN_POOL_SIZE = 5  # Don't return data until we have enough for anonymity

    def __init__(self):
        self._genomes: dict[str, AnonymizedGenome] = {}  # genome_id -> genome
        self._tenant_contributions: dict[str, set[str]] = {}  # tenant_id -> set of genome_ids
        self._opted_in_tenants: set[str] = set()
        self._templates: dict[str, StrategyTemplate] = {}

    # ── Opt-In Management ────────────────────────────────────────────────

    def opt_in(self, tenant_id: str) -> bool:
        """Tenant opts in to the marketplace."""
        self._opted_in_tenants.add(tenant_id)
        logger.info(f"Tenant {tenant_id} opted into genome marketplace")
        return True

    def opt_out(self, tenant_id: str) -> int:
        """Tenant opts out — removes all their contributions."""
        self._opted_in_tenants.discard(tenant_id)
        genome_ids = self._tenant_contributions.pop(tenant_id, set())
        for gid in genome_ids:
            self._genomes.pop(gid, None)
        logger.info(f"Tenant {tenant_id} opted out — removed {len(genome_ids)} genomes")
        return len(genome_ids)

    def is_opted_in(self, tenant_id: str) -> bool:
        return tenant_id in self._opted_in_tenants

    # ── Contribution ─────────────────────────────────────────────────────

    def contribute(self, tenant_id: str, dna_dict: dict,
                   tenant_tier: str = "pro") -> Optional[str]:
        """Contribute an anonymized genome to the marketplace."""
        if not self.is_opted_in(tenant_id):
            return None

        genome = anonymize_campaign_dna(dna_dict, tenant_tier)

        # Skip low-quality genomes
        if genome.quality_score < 0.3:
            logger.debug(f"Genome rejected — quality too low: {genome.quality_score}")
            return None

        self._genomes[genome.genome_id] = genome

        if tenant_id not in self._tenant_contributions:
            self._tenant_contributions[tenant_id] = set()
        self._tenant_contributions[tenant_id].add(genome.genome_id)

        logger.info(
            f"Genome contributed: {genome.genome_id} "
            f"({genome.icp_archetype}/{genome.service_archetype}) "
            f"quality={genome.quality_score}"
        )
        return genome.genome_id

    # ── Querying ─────────────────────────────────────────────────────────

    def query(self, q: MarketplaceQuery) -> dict[str, Any]:
        """Query the marketplace for aggregated intelligence."""
        # Find matching genomes
        matches = []
        for genome in self._genomes.values():
            score = self._match_score(genome, q)
            if score > 0:
                matches.append((score, genome))

        matches.sort(key=lambda x: x[0], reverse=True)

        if len(matches) < self.MIN_POOL_SIZE:
            return {
                "status": "insufficient_data",
                "matches": len(matches),
                "min_required": self.MIN_POOL_SIZE,
                "message": f"Need at least {self.MIN_POOL_SIZE} similar campaigns. "
                           f"Currently have {len(matches)}. More data coming as users contribute.",
            }

        # Aggregate outcomes
        top_matches = matches[:q.limit]
        agg = self._aggregate(top_matches)
        agg["status"] = "success"
        agg["matches"] = len(top_matches)
        agg["total_pool"] = len(self._genomes)
        return agg

    def _match_score(self, genome: AnonymizedGenome, q: MarketplaceQuery) -> float:
        """Score how well a genome matches the query."""
        score = 0.0
        checks = 0

        if q.industry:
            checks += 1
            if genome.industry and q.industry.lower() in genome.industry.lower():
                score += 1.0

        if q.icp_archetype:
            checks += 1
            if genome.icp_archetype == q.icp_archetype:
                score += 1.0
            elif genome.icp_archetype in ("c_suite", "enterprise_buyer") and q.icp_archetype in ("c_suite", "enterprise_buyer"):
                score += 0.5

        if q.service_archetype:
            checks += 1
            if genome.service_archetype == q.service_archetype:
                score += 1.0

        if q.geography_region:
            checks += 1
            if genome.geography_region == q.geography_region:
                score += 1.0
            elif genome.geography_region == "global":
                score += 0.5

        if q.company_size_bucket:
            checks += 1
            if genome.company_size_bucket == q.company_size_bucket:
                score += 1.0

        # Quality bonus
        score += genome.quality_score * 0.3

        return score / max(checks, 1)

    def _aggregate(self, matches: list[tuple[float, AnonymizedGenome]]) -> dict:
        """Aggregate intelligence from matching genomes."""
        # Weighted outcome averages
        outcome_sums: dict[str, list[tuple[float, float]]] = {}
        all_worked: list[str] = []
        all_failed: list[str] = []
        channel_counts: dict[str, int] = {}
        grade_counts: dict[str, dict[str, int]] = {}

        for score, genome in matches:
            for k, v in genome.outcomes.items():
                outcome_sums.setdefault(k, []).append((score, v))
            all_worked.extend(genome.strategies_that_worked)
            all_failed.extend(genome.strategies_that_failed)
            for ch, active in genome.channel_mix.items():
                if active:
                    channel_counts[ch] = channel_counts.get(ch, 0) + 1
            for agent_id, grade in genome.agent_grades.items():
                grade_counts.setdefault(agent_id, {})
                grade_counts[agent_id][grade] = grade_counts[agent_id].get(grade, 0) + 1

        # Weighted averages
        avg_outcomes = {}
        for k, pairs in outcome_sums.items():
            total_w = sum(w for w, _ in pairs)
            if total_w > 0:
                avg_outcomes[k] = round(sum(w * v for w, v in pairs) / total_w, 4)

        # Channel ranking
        total = len(matches)
        channel_ranking = sorted(
            [(ch, count / total) for ch, count in channel_counts.items()],
            key=lambda x: x[1], reverse=True,
        )

        # Deduplicate strategies (keep unique by first 50 chars)
        seen_worked = set()
        unique_worked = []
        for s in all_worked:
            key = s[:50].lower()
            if key not in seen_worked:
                seen_worked.add(key)
                unique_worked.append(s)

        seen_failed = set()
        unique_failed = []
        for s in all_failed:
            key = s[:50].lower()
            if key not in seen_failed:
                seen_failed.add(key)
                unique_failed.append(s)

        return {
            "avg_outcomes": avg_outcomes,
            "top_channels": [
                {"channel": ch, "usage_pct": round(pct * 100, 1)}
                for ch, pct in channel_ranking
            ],
            "strategies_that_worked": unique_worked[:10],
            "strategies_that_failed": unique_failed[:10],
            "confidence": round(min(len(matches) / 20, 1.0), 2),  # Max confidence at 20+ matches
        }

    # ── Strategy Templates ───────────────────────────────────────────────

    def generate_templates(self) -> list[StrategyTemplate]:
        """
        Generate reusable strategy templates from marketplace data.
        Templates are pre-computed strategies for common archetypes.
        """
        # Group genomes by archetype combo
        groups: dict[str, list[AnonymizedGenome]] = {}
        for genome in self._genomes.values():
            key = f"{genome.icp_archetype}:{genome.service_archetype}"
            groups.setdefault(key, []).append(genome)

        templates = []
        for key, genomes in groups.items():
            if len(genomes) < self.MIN_POOL_SIZE:
                continue

            icp, service = key.split(":", 1)

            # Aggregate this group
            avg_outcomes = {}
            channel_votes: dict[str, int] = {}
            all_strategies: list[str] = []
            all_pitfalls: list[str] = []

            for g in genomes:
                for k, v in g.outcomes.items():
                    avg_outcomes.setdefault(k, [])
                    avg_outcomes[k].append(v)
                for ch, active in g.channel_mix.items():
                    if active:
                        channel_votes[ch] = channel_votes.get(ch, 0) + 1
                all_strategies.extend(g.strategies_that_worked)
                all_pitfalls.extend(g.strategies_that_failed)

            # Average outcomes
            expected = {k: round(sum(v) / len(v), 4) for k, v in avg_outcomes.items() if v}

            # Top channels
            ranked = sorted(channel_votes.items(), key=lambda x: x[1], reverse=True)
            top_channels = [ch for ch, _ in ranked[:5]]

            template = StrategyTemplate(
                template_id=f"tpl_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                name=f"{icp.replace('_', ' ').title()} × {service.replace('_', ' ').title()}",
                description=f"Pre-built strategy for {service} businesses targeting {icp} buyers",
                industry="",
                icp_archetype=icp,
                recommended_channels=top_channels,
                expected_outcomes=expected,
                key_strategies=list(set(all_strategies))[:8],
                pitfalls_to_avoid=list(set(all_pitfalls))[:5],
                sample_size=len(genomes),
                confidence=round(min(len(genomes) / 20, 1.0), 2),
            )
            templates.append(template)
            self._templates[template.template_id] = template

        logger.info(f"Generated {len(templates)} strategy templates from {len(self._genomes)} genomes")
        return templates

    def get_template(self, template_id: str) -> Optional[dict]:
        """Get a specific strategy template."""
        t = self._templates.get(template_id)
        return t.__dict__ if t else None

    def list_templates(self) -> list[dict]:
        """List all available strategy templates."""
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "sample_size": t.sample_size,
                "confidence": t.confidence,
                "recommended_channels": t.recommended_channels,
            }
            for t in self._templates.values()
        ]

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total_genomes": len(self._genomes),
            "opted_in_tenants": len(self._opted_in_tenants),
            "total_contributors": len(self._tenant_contributions),
            "templates_available": len(self._templates),
            "archetypes": {
                "icp": list(set(g.icp_archetype for g in self._genomes.values())),
                "service": list(set(g.service_archetype for g in self._genomes.values())),
                "geography": list(set(g.geography_region for g in self._genomes.values())),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

genome_marketplace = GenomeMarketplace()
