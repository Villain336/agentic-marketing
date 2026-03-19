"""
Press releases, journalist pitches, and media monitoring.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _draft_press_release(headline: str, body: str, company: str = "", quote_attribution: str = "", boilerplate: str = "") -> str:
    """Generate AP-style press release."""
    return json.dumps({
        "format": "AP Style Press Release",
        "headline": headline,
        "dateline": f"[CITY, STATE] — {company or 'Company'}",
        "lead": body[:300] if body else "Opening paragraph with key news angle.",
        "quote": f'"{body[300:500] if len(body) > 300 else "Quote placeholder."}" — {quote_attribution or "Founder/CEO"}',
        "boilerplate": boilerplate or f"About {company}: [Company description, founding year, key stats, website]",
        "contact": "Media Contact: [Name] | [Email] | [Phone]",
        "distribution_recommendations": [
            "PR Newswire or Business Wire for broad distribution",
            "Direct email to target journalists",
            "Post on company newsroom/blog",
            "Share on LinkedIn and X",
        ],
    })



async def _pitch_journalist(journalist_name: str, publication: str, angle: str, recent_article: str = "") -> str:
    """Create personalized journalist pitch."""
    return json.dumps({
        "to": journalist_name,
        "publication": publication,
        "angle": angle,
        "personalization": f"Reference their recent article: '{recent_article}'" if recent_article else "Research their recent work and reference it",
        "pitch_template": {
            "subject": f"[Pitch] {angle[:60]}",
            "opening": f"Hi {journalist_name.split()[0] if journalist_name else 'there'},",
            "hook": f"Quick pitch: {angle}",
            "why_now": "Tie to current news cycle or trend",
            "offer": "Expert commentary, data, exclusive access — whatever serves the story",
            "closing": "Happy to hop on a quick call or send more details. No worries if it's not a fit.",
        },
        "best_practices": [
            "Keep under 150 words", "Lead with what THEY care about, not what you want",
            "Subject line: specific, not clickbait", "Follow up once after 3-5 days, then stop",
        ],
    })



async def _media_monitor(brand_name: str, competitors: str = "", keywords: str = "") -> str:
    """Set up media monitoring for brand mentions and sentiment."""
    competitor_list = [c.strip() for c in competitors.split(",")] if competitors else []
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []

    if settings.newsapi_key:
        # Build query: brand + competitors
        query_parts = [f'"{brand_name}"']
        for comp in competitor_list[:3]:
            if comp:
                query_parts.append(f'"{comp}"')
        query = " OR ".join(query_parts)
        try:
            resp = await _http.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "apiKey": settings.newsapi_key,
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "language": "en",
                },
            )
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                news_items = [
                    {
                        "title": a.get("title"),
                        "source": a.get("source", {}).get("name"),
                        "published_at": a.get("publishedAt"),
                        "url": a.get("url"),
                        "description": a.get("description"),
                        "mentions_brand": brand_name.lower() in (a.get("title") or "").lower() or brand_name.lower() in (a.get("description") or "").lower(),
                        "mentions_competitor": any(c.lower() in (a.get("title") or "").lower() for c in competitor_list if c),
                    }
                    for a in articles
                ]
                return json.dumps({
                    "brand": brand_name,
                    "monitoring_config": {
                        "brand_mentions": [brand_name, brand_name.lower(), brand_name.replace(" ", "")],
                        "competitor_mentions": competitor_list,
                        "industry_keywords": keyword_list,
                        "channels": ["news", "blogs", "social_media", "reddit", "hackernews", "podcasts"],
                        "sentiment_tracking": True,
                        "alert_triggers": ["negative_sentiment_spike", "competitor_mention_surge", "crisis_keywords"],
                    },
                    "articles": news_items,
                    "total_articles_found": len(articles),
                    "recommended_tools": [
                        "Google Alerts (free)", "Mention.com", "Brand24", "Meltwater",
                        "BuzzSumo for content mentions", "Social Searcher for social mentions",
                    ],
                    "note": f"Live media monitoring via NewsAPI — {len(articles)} articles found.",
                })
            else:
                logger.warning("NewsAPI returned %s for media monitor, falling back to stub", resp.status_code)
        except Exception as exc:
            logger.warning("NewsAPI error for media monitor: %s", exc)

    # --- Stub fallback ---
    return json.dumps({
        "brand": brand_name,
        "monitoring_config": {
            "brand_mentions": [brand_name, brand_name.lower(), brand_name.replace(" ", "")],
            "competitor_mentions": competitor_list,
            "industry_keywords": keyword_list,
            "channels": ["news", "blogs", "social_media", "reddit", "hackernews", "podcasts"],
            "sentiment_tracking": True,
            "alert_triggers": ["negative_sentiment_spike", "competitor_mention_surge", "crisis_keywords"],
        },
        "recommended_tools": [
            "Google Alerts (free)", "Mention.com", "Brand24", "Meltwater",
            "BuzzSumo for content mentions", "Social Searcher for social mentions",
        ],
        "note": "Stub config — configure NEWSAPI_KEY for live brand mention tracking.",
    })



def register_pr_tools(registry):
    """Register all pr tools with the given registry."""
    from models import ToolParameter

    registry.register("draft_press_release", "Generate AP-style press release with distribution recommendations.",
        [ToolParameter(name="headline", description="Press release headline"),
         ToolParameter(name="body", description="Key announcement text"),
         ToolParameter(name="company", description="Company name", required=False),
         ToolParameter(name="quote_attribution", description="Name/title for quote", required=False),
         ToolParameter(name="boilerplate", description="Company boilerplate text", required=False)],
        _draft_press_release, "pr")

    registry.register("pitch_journalist", "Create personalized journalist pitch with research-backed angles.",
        [ToolParameter(name="journalist_name", description="Journalist's name"),
         ToolParameter(name="publication", description="Publication name"),
         ToolParameter(name="angle", description="Story angle/pitch"),
         ToolParameter(name="recent_article", description="Reference to their recent work", required=False)],
        _pitch_journalist, "pr")

    registry.register("media_monitor", "Set up media monitoring for brand mentions, sentiment, and competitor tracking.",
        [ToolParameter(name="brand_name", description="Brand name to monitor"),
         ToolParameter(name="competitors", description="Comma-separated competitor names", required=False),
         ToolParameter(name="keywords", description="Additional keywords to track", required=False)],
        _media_monitor, "pr")

    # ── Data Engineering & Dashboard Tools ──

