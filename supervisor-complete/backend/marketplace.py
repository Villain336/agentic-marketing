"""
Supervisor Backend — SkillHub Community Marketplace
Users publish, discover, and install agent skills, templates, and workflows.
Competes with OpenClaw's ClawHub marketplace.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.marketplace")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class MarketplaceListing(BaseModel):
    """A published item on the SkillHub marketplace."""
    id: str = Field(default_factory=lambda: f"mkt_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")
    type: str = "skill"                  # skill | template | workflow | agent_config
    name: str
    description: str
    long_description: str = ""
    author_user_id: str = ""
    author_name: str = "Community"
    version: str = "1.0.0"
    category: str = "general"            # marketing | sales | ops | finance | custom
    tags: list[str] = []
    icon: str = ""

    # Content payload
    payload: dict = {}                    # The actual skill/template/workflow definition

    # Marketplace metadata
    installs: int = 0
    rating: float = 0.0
    rating_count: int = 0
    is_verified: bool = False             # Reviewed by platform team
    is_featured: bool = False
    price: float = 0.0                    # 0 = free
    revenue_share_pct: float = 70.0       # Creator gets 70%, platform 30%

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MarketplaceReview(BaseModel):
    """User review of a marketplace listing."""
    id: str = Field(default_factory=lambda: f"rev_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")
    listing_id: str
    user_id: str
    rating: int = 5                       # 1-5
    comment: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InstalledItem(BaseModel):
    """Record of a user installing a marketplace item."""
    listing_id: str
    user_id: str
    campaign_id: str = ""
    installed_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class SkillHubMarketplace:
    """
    Community marketplace for sharing agent skills, templates, and workflows.
    Supports free + paid listings, ratings, reviews, and install tracking.
    """

    CATEGORIES = [
        "marketing", "sales", "operations", "finance", "legal",
        "content", "seo", "social", "ads", "analytics", "custom",
    ]

    def __init__(self):
        self._listings: dict[str, MarketplaceListing] = {}
        self._reviews: dict[str, list[MarketplaceReview]] = {}  # listing_id -> reviews
        self._installs: list[InstalledItem] = []
        self._user_installs: dict[str, list[str]] = {}  # user_id -> [listing_ids]

        # Seed with built-in marketplace items
        self._seed_marketplace()

    def _seed_marketplace(self):
        """Pre-populate with platform-built skills."""
        seeds = [
            MarketplaceListing(
                type="workflow", name="Cold Outreach Optimizer",
                description="Automatically A/B tests subject lines, optimizes send times, and escalates high-intent replies",
                category="sales", tags=["outreach", "email", "optimization"],
                icon="mail", is_verified=True, is_featured=True,
                payload={"steps": ["prospector", "outreach", "sensing_monitor"], "auto_optimize": True},
            ),
            MarketplaceListing(
                type="workflow", name="SEO Content Machine",
                description="Keyword research → content brief → article → publish → monitor rankings",
                category="content", tags=["seo", "content", "blog"],
                icon="file-text", is_verified=True, is_featured=True,
                payload={"steps": ["seo_keyword_research", "content", "publish_to_cms", "analytics_monitor"]},
            ),
            MarketplaceListing(
                type="skill", name="Competitor Price Tracker",
                description="Monitors competitor pricing pages daily and alerts on changes",
                category="analytics", tags=["competitive", "pricing", "monitoring"],
                icon="coins", is_verified=True,
                payload={"implementation_type": "composite", "steps": [
                    {"type": "tool", "tool": "web_scrape", "inputs": {"url": "{{competitor_url}}"}},
                    {"type": "llm", "prompt": "Extract pricing from: {{tool_output}}"},
                ]},
            ),
            MarketplaceListing(
                type="template", name="SaaS Product Launch",
                description="Complete launch playbook: landing page, email list, social teasers, PR outreach, launch day automation",
                category="marketing", tags=["launch", "saas", "product"],
                icon="rocket", is_verified=True, is_featured=True,
                payload={"agents": ["sitelaunch", "content", "social", "outreach", "pr_comms", "newsletter"]},
            ),
            MarketplaceListing(
                type="agent_config", name="LinkedIn Growth Hacker",
                description="Custom agent config: posts 3x/week, engages with ICP comments, tracks follower growth",
                category="social", tags=["linkedin", "growth", "engagement"],
                icon="briefcase", is_verified=True,
                payload={"base_agent": "social", "schedule": "3x_weekly",
                         "channels": ["linkedin"], "auto_engage": True},
            ),
            MarketplaceListing(
                type="workflow", name="Revenue Recovery Autopilot",
                description="Detects failed payments → sends dunning emails → escalates to phone → offers payment plans",
                category="finance", tags=["billing", "dunning", "revenue"],
                icon="credit-card", is_verified=True,
                payload={"steps": ["billing_check", "email_dunning", "phone_escalation", "payment_plan_offer"]},
            ),
        ]

        for item in seeds:
            self._listings[item.id] = item

    def publish(self, listing: MarketplaceListing) -> MarketplaceListing:
        """Publish a new item to the marketplace."""
        if listing.category not in self.CATEGORIES:
            listing.category = "custom"
        self._listings[listing.id] = listing
        logger.info(f"Published to marketplace: {listing.name} ({listing.type})")
        return listing

    def update_listing(self, listing_id: str, **updates) -> Optional[MarketplaceListing]:
        listing = self._listings.get(listing_id)
        if not listing:
            return None
        for k, v in updates.items():
            if hasattr(listing, k):
                setattr(listing, k, v)
        listing.updated_at = datetime.utcnow()
        return listing

    def get_listing(self, listing_id: str) -> Optional[MarketplaceListing]:
        return self._listings.get(listing_id)

    def search(self, query: str = "", category: str = "", item_type: str = "",
               tags: list[str] = None, sort_by: str = "installs",
               limit: int = 20, offset: int = 0) -> dict:
        """Search the marketplace with filters."""
        results = list(self._listings.values())

        if query:
            q = query.lower()
            results = [r for r in results if q in r.name.lower() or q in r.description.lower()
                       or any(q in t for t in r.tags)]

        if category:
            results = [r for r in results if r.category == category]

        if item_type:
            results = [r for r in results if r.type == item_type]

        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]

        # Sort
        if sort_by == "installs":
            results.sort(key=lambda r: r.installs, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda r: r.rating, reverse=True)
        elif sort_by == "newest":
            results.sort(key=lambda r: r.created_at, reverse=True)
        elif sort_by == "price_low":
            results.sort(key=lambda r: r.price)

        total = len(results)
        results = results[offset:offset + limit]

        return {
            "total": total,
            "results": [r.model_dump() for r in results],
            "offset": offset,
            "limit": limit,
        }

    def install(self, listing_id: str, user_id: str, campaign_id: str = "") -> Optional[InstalledItem]:
        """Install a marketplace item for a user/campaign."""
        listing = self._listings.get(listing_id)
        if not listing:
            return None

        item = InstalledItem(
            listing_id=listing_id, user_id=user_id,
            campaign_id=campaign_id, version=listing.version,
        )
        self._installs.append(item)

        if user_id not in self._user_installs:
            self._user_installs[user_id] = []
        if listing_id not in self._user_installs[user_id]:
            self._user_installs[user_id].append(listing_id)

        listing.installs += 1
        logger.info(f"User {user_id} installed {listing.name}")
        return item

    def uninstall(self, listing_id: str, user_id: str) -> bool:
        if user_id in self._user_installs:
            if listing_id in self._user_installs[user_id]:
                self._user_installs[user_id].remove(listing_id)
                listing = self._listings.get(listing_id)
                if listing:
                    listing.installs = max(0, listing.installs - 1)
                return True
        return False

    def get_user_installs(self, user_id: str) -> list[MarketplaceListing]:
        ids = self._user_installs.get(user_id, [])
        return [self._listings[lid] for lid in ids if lid in self._listings]

    def add_review(self, listing_id: str, user_id: str, rating: int,
                   comment: str = "") -> Optional[MarketplaceReview]:
        """Add a review to a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            return None

        rating = max(1, min(5, rating))
        review = MarketplaceReview(
            listing_id=listing_id, user_id=user_id,
            rating=rating, comment=comment,
        )

        if listing_id not in self._reviews:
            self._reviews[listing_id] = []
        self._reviews[listing_id].append(review)

        # Update average rating
        reviews = self._reviews[listing_id]
        listing.rating = sum(r.rating for r in reviews) / len(reviews)
        listing.rating_count = len(reviews)

        return review

    def get_reviews(self, listing_id: str) -> list[MarketplaceReview]:
        return self._reviews.get(listing_id, [])

    def get_featured(self) -> list[MarketplaceListing]:
        return [l for l in self._listings.values() if l.is_featured]

    def get_categories_summary(self) -> list[dict]:
        """Get listing counts per category."""
        counts: dict[str, int] = {}
        for listing in self._listings.values():
            counts[listing.category] = counts.get(listing.category, 0) + 1
        return [{"category": c, "count": counts.get(c, 0)} for c in self.CATEGORIES]

    def get_creator_earnings(self, user_id: str) -> dict:
        """Get earnings summary for a marketplace creator."""
        user_listings = [l for l in self._listings.values() if l.author_user_id == user_id]
        total_installs = sum(l.installs for l in user_listings)
        total_revenue = sum(l.price * l.installs * (l.revenue_share_pct / 100) for l in user_listings)
        return {
            "listings_count": len(user_listings),
            "total_installs": total_installs,
            "total_earnings": total_revenue,
            "listings": [{"name": l.name, "installs": l.installs,
                          "earnings": l.price * l.installs * (l.revenue_share_pct / 100)}
                         for l in user_listings],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

skillhub = SkillHubMarketplace()
