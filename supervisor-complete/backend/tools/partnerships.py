"""
Partner identification, UGC briefs, partnership agreements, and creator discovery.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _identify_partners(business_name: str, service: str, partner_type: str = "all") -> str:
    """Map the partnership landscape."""
    types = {
        "technology": "Tech integrations, API partners, platform ecosystems",
        "channel": "Resellers, agencies, consultants who sell to your ICP",
        "strategic": "Complementary services for co-marketing and bundling",
        "distribution": "Marketplaces, directories, aggregators for reach",
    }
    return json.dumps({
        "business": business_name,
        "service": service,
        "partner_types": types if partner_type == "all" else {partner_type: types.get(partner_type, "")},
        "discovery_method": "Use web_search to find: '[service] integrations', '[ICP] consultants', 'best [industry] tools'",
        "evaluation_criteria": ["ICP overlap", "Brand alignment", "Revenue potential", "Effort to maintain", "Exclusivity requirements"],
    })



async def _create_ugc_brief(brand_name: str, product: str, content_type: str = "social", budget: str = "", guidelines: str = "") -> str:
    """Generate UGC creator collaboration brief."""
    return json.dumps({
        "brief": {
            "brand": brand_name,
            "product": product,
            "content_type": content_type,
            "deliverables": {
                "social": "1 Reel/TikTok (15-60s) + 3 Stories + 1 Feed Post",
                "review": "Written review (500+ words) + unboxing video",
                "testimonial": "60s video testimonial + written quote",
            }.get(content_type, content_type),
            "content_guidelines": guidelines or "Authentic, unscripted feel. Show genuine experience. Include CTA.",
            "usage_rights": "Perpetual, worldwide rights for owned and paid channels",
            "compensation": budget or "Product gifting + $200-500 per creator (micro-tier)",
        },
        "creator_tiers": {
            "nano": {"followers": "1K-10K", "rate": "$50-200", "best_for": "Authenticity, niche communities"},
            "micro": {"followers": "10K-50K", "rate": "$200-1000", "best_for": "Engagement, targeted reach"},
            "mid": {"followers": "50K-500K", "rate": "$1000-5000", "best_for": "Scale + credibility"},
        },
    })



async def _draft_partnership_agreement(partner_name: str, structure: str = "revenue_share", terms: str = "") -> str:
    """Create partnership term sheet."""
    structures = {
        "revenue_share": {"split": "20-30% of referred revenue", "attribution": "UTM/cookie 90-day window", "payout": "Monthly net-30"},
        "co_marketing": {"commitment": "Quarterly joint content", "cost_split": "50/50", "lead_sharing": "Mutual opt-in"},
        "white_label": {"margin": "40-60% white-label markup", "support": "L2 escalation to original provider", "branding": "Partner's brand only"},
        "integration": {"api_access": "Partner API key", "support_tier": "Dedicated integration support", "listing": "Marketplace/directory listing"},
    }
    return json.dumps({
        "partner": partner_name,
        "structure": structure,
        "terms": structures.get(structure, {"custom": terms}),
        "standard_clauses": ["Term and termination", "Non-compete scope", "Confidentiality", "IP ownership", "Liability caps", "Dispute resolution"],
        "note": "Term sheet draft — must be reviewed by legal counsel before execution.",
    })



async def _discover_creators(niche: str, platform: str = "all", min_followers: str = "1000") -> str:
    """Find relevant UGC creators and influencers."""
    yt_api_key = getattr(settings, 'youtube_api_key', '')
    if yt_api_key and platform in ("all", "youtube"):
        try:
            import urllib.parse
            search_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&type=channel&q={urllib.parse.quote(niche)}&maxResults=10&key={yt_api_key}"
            )
            search_resp = await _http.get(search_url)
            if search_resp.status_code == 200:
                items = search_resp.json().get("items", [])
                channel_ids = [i["id"]["channelId"] for i in items if i.get("id", {}).get("channelId")]
                channels = []
                if channel_ids:
                    stats_url = (
                        f"https://www.googleapis.com/youtube/v3/channels"
                        f"?part=statistics,snippet&id={','.join(channel_ids)}&key={yt_api_key}"
                    )
                    stats_resp = await _http.get(stats_url)
                    if stats_resp.status_code == 200:
                        try:
                            min_subs = int(str(min_followers).replace(",", "").replace("k", "000").replace("K", "000"))
                        except (ValueError, AttributeError):
                            min_subs = 1000
                        for ch in stats_resp.json().get("items", []):
                            stats = ch.get("statistics", {})
                            snippet = ch.get("snippet", {})
                            sub_count = int(stats.get("subscriberCount", 0))
                            if sub_count >= min_subs:
                                channels.append({
                                    "channel_id": ch["id"],
                                    "name": snippet.get("title", ""),
                                    "description": snippet.get("description", "")[:200],
                                    "subscribers": sub_count,
                                    "video_count": int(stats.get("videoCount", 0)),
                                    "view_count": int(stats.get("viewCount", 0)),
                                    "url": f"https://youtube.com/channel/{ch['id']}",
                                    "country": snippet.get("country", ""),
                                })
                if channels:
                    channels.sort(key=lambda c: c["subscribers"], reverse=True)
                    return json.dumps({
                        "niche": niche,
                        "platform": "youtube",
                        "min_followers": min_followers,
                        "creators": channels,
                        "count": len(channels),
                        "evaluation_criteria": [
                            "Engagement rate > 3% (more important than subscriber count)",
                            "Audience demographics match ICP",
                            "Brand safety — review recent content",
                            "Previous brand collaborations (check for competitor conflicts)",
                        ],
                    })
        except Exception as e:
            logger.warning(f"YouTube creator discovery failed: {e}")

    # Stub fallback
    return json.dumps({
        "niche": niche,
        "platform": platform,
        "min_followers": min_followers,
        "discovery_methods": [
            f"Search '{niche}' on TikTok/Instagram/YouTube and sort by engagement rate",
            f"Use web_search: '{niche} influencers {platform}' or '{niche} content creators'",
            "Check competitor tagged posts and collaborations",
            "Search Reddit/Twitter for passionate community members",
            "Use tools: Heepsy, Upfluence, CreatorIQ, or AspireIQ for scaled discovery",
        ],
        "evaluation_criteria": [
            "Engagement rate > 3% (more important than follower count)",
            "Content quality and consistency",
            "Audience demographics match ICP",
            "Brand safety — review recent content",
            "Previous brand collaborations (check for competitor conflicts)",
        ],
        "note": "Configure YOUTUBE_API_KEY for live YouTube channel discovery.",
    })



async def _industry_association_research(industry: str, geography: str = "us") -> str:
    """Find relevant trade groups, associations, and lobbying opportunities."""
    return json.dumps({
        "industry": industry,
        "geography": geography,
        "research_framework": {
            "trade_associations": f"Search: '{industry} trade association {geography}', '{industry} industry group'",
            "chambers_of_commerce": "Local, state, and national chambers — networking + advocacy",
            "standards_bodies": f"Search: '{industry} standards organization', '{industry} certification body'",
            "advisory_boards": f"Search: '{industry} advisory board', '{industry} council'",
            "lobbying_coalitions": f"Search: '{industry} advocacy group', '{industry} lobbying coalition'",
        },
        "engagement_levels": [
            "Member (annual dues, directory listing, event access)",
            "Committee member (influence policy, deeper networking)",
            "Board member (leadership position, high visibility)",
            "Sponsor (event/content sponsorship, brand exposure)",
            "Advocate (testify, comment on regulations, media spokesperson)",
        ],
        "lobbying_considerations": [
            "Register as lobbyist if spending exceeds state thresholds",
            "Track lobbying expenses for tax purposes (generally not deductible)",
            "Build coalitions with aligned businesses for amplified voice",
            "Engage with proposed regulations during public comment periods",
        ],
    })



def register_partnerships_tools(registry):
    """Register all partnerships tools with the given registry."""
    from models import ToolParameter

    registry.register("identify_partners", "Map the partnership landscape — technology, channel, strategic, distribution partners.",
        [ToolParameter(name="business_name", description="Business name"),
         ToolParameter(name="service", description="Service offered"),
         ToolParameter(name="partner_type", description="Type: technology, channel, strategic, distribution, all", required=False)],
        _identify_partners, "partnerships")

    registry.register("create_ugc_brief", "Generate UGC creator collaboration brief with deliverables and compensation.",
        [ToolParameter(name="brand_name", description="Brand name"),
         ToolParameter(name="product", description="Product or service to promote"),
         ToolParameter(name="content_type", description="Type: social, review, testimonial", required=False),
         ToolParameter(name="budget", description="Budget per creator", required=False),
         ToolParameter(name="guidelines", description="Content guidelines", required=False)],
        _create_ugc_brief, "partnerships")

    registry.register("draft_partnership_agreement", "Create partnership term sheet with standard clauses.",
        [ToolParameter(name="partner_name", description="Partner company name"),
         ToolParameter(name="structure", description="Structure: revenue_share, co_marketing, white_label, integration", required=False),
         ToolParameter(name="terms", description="Custom terms", required=False)],
        _draft_partnership_agreement, "partnerships")

    registry.register("discover_creators", "Find relevant UGC creators and influencers by niche and platform.",
        [ToolParameter(name="niche", description="Content niche or industry"),
         ToolParameter(name="platform", description="Platform: tiktok, instagram, youtube, twitter, all", required=False),
         ToolParameter(name="min_followers", description="Minimum follower count", required=False)],
        _discover_creators, "partnerships")

    registry.register("industry_association_research", "Find relevant trade groups, chambers, and lobbying opportunities.",
        [ToolParameter(name="industry", description="Industry to research"),
         ToolParameter(name="geography", description="Geography: us, state name, or country", required=False)],
        _industry_association_research, "partnerships")

    # ── Client Fulfillment Tools ──

