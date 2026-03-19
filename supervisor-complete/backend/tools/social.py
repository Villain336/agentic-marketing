"""
Twitter, LinkedIn, Instagram, Buffer, and social analytics tools.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _post_twitter(text: str, media_ids: str = "") -> str:
    bearer = getattr(settings, 'twitter_bearer_token', '') or ""
    if not bearer:
        return json.dumps({"error": "Twitter API not configured. Set TWITTER_BEARER_TOKEN."})
    payload: dict[str, Any] = {"text": text[:280]}
    if media_ids:
        payload["media"] = {"media_ids": [m.strip() for m in media_ids.split(",")]}
    try:
        resp = await _http.post("https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"posted": True, "tweet_id": data.get("data", {}).get("id", "")})
        return json.dumps({"posted": False, "error": f"Twitter {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"posted": False, "error": str(e)})



async def _search_twitter(query: str, max_results: int = 10) -> str:
    bearer = getattr(settings, 'twitter_bearer_token', '') or ""
    if not bearer:
        return json.dumps({"error": "Twitter API not configured."})
    try:
        resp = await _http.get("https://api.twitter.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {bearer}"},
            params={"query": query, "max_results": min(max_results, 100),
                    "tweet.fields": "author_id,created_at,public_metrics"})
        if resp.status_code == 200:
            data = resp.json()
            tweets = [{"id": t["id"], "text": t["text"][:200],
                       "metrics": t.get("public_metrics", {})}
                      for t in data.get("data", [])[:max_results]]
            return json.dumps({"query": query, "count": len(tweets), "tweets": tweets})
        return json.dumps({"error": f"Twitter {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _post_linkedin(text: str, image_url: str = "") -> str:
    client_id = getattr(settings, 'linkedin_client_id', '') or ""
    if not client_id:
        return json.dumps({"error": "LinkedIn API not configured. Set LINKEDIN_CLIENT_ID."})
    return json.dumps({"posted": False, "note": "LinkedIn posting requires OAuth flow. Content prepared.",
                       "content": text[:500]})



async def _post_instagram(caption: str, image_url: str) -> str:
    """Post to Instagram via Meta Graph API (requires Business account)."""
    token = getattr(settings, 'meta_access_token', '') or ""
    ig_account_id = getattr(settings, 'instagram_business_id', '') or ""
    if not token or not ig_account_id:
        return json.dumps({"error": "Instagram not configured. Set META_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID.",
                           "draft": {"caption": caption[:200], "image_url": image_url}})
    try:
        create_resp = await _http.post(f"https://graph.facebook.com/v19.0/{ig_account_id}/media",
            params={"access_token": token, "caption": caption, "image_url": image_url})
        if create_resp.status_code == 200:
            creation_id = create_resp.json().get("id", "")
            publish_resp = await _http.post(f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish",
                params={"access_token": token, "creation_id": creation_id})
            if publish_resp.status_code == 200:
                return json.dumps({"posted": True, "media_id": publish_resp.json().get("id", ""),
                                   "platform": "instagram"})
        return json.dumps({"error": f"Instagram API error: {create_resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _schedule_social_post(platform: str, text: str, scheduled_time: str,
                                  image_url: str = "") -> str:
    """Schedule a social post via Buffer API."""
    buffer_key = getattr(settings, 'buffer_api_key', '') or ""
    if not buffer_key:
        return json.dumps({"error": "Buffer not configured. Set BUFFER_API_KEY.",
                           "draft": {"platform": platform, "text": text[:200],
                                     "scheduled_time": scheduled_time}})
    try:
        resp = await _http.get("https://api.bufferapp.com/1/profiles.json",
            params={"access_token": buffer_key})
        profiles = resp.json() if resp.status_code == 200 else []
        profile_id = ""
        for p in profiles:
            if platform.lower() in p.get("service", "").lower():
                profile_id = p.get("id", "")
                break
        if not profile_id:
            return json.dumps({"error": f"No Buffer profile found for {platform}"})
        payload: dict[str, Any] = {
            "access_token": buffer_key,
            "profile_ids[]": profile_id,
            "text": text,
            "scheduled_at": scheduled_time,
        }
        if image_url:
            payload["media[photo]"] = image_url
        resp = await _http.post("https://api.bufferapp.com/1/updates/create.json", data=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"scheduled": True, "update_id": data.get("updates", [{}])[0].get("id", ""),
                               "platform": platform, "scheduled_time": scheduled_time})
        return json.dumps({"error": f"Buffer {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _get_social_analytics(platform: str, period: str = "7d") -> str:
    """Get social media engagement metrics for a platform."""
    if platform == "twitter":
        bearer = getattr(settings, 'twitter_bearer_token', '') or ""
        if not bearer:
            return json.dumps({"error": "Twitter not configured."})
        try:
            resp = await _http.get("https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {bearer}"},
                params={"user.fields": "public_metrics"})
            if resp.status_code == 200:
                metrics = resp.json().get("data", {}).get("public_metrics", {})
                return json.dumps({"platform": "twitter", "followers": metrics.get("followers_count", 0),
                                   "following": metrics.get("following_count", 0),
                                   "tweets": metrics.get("tweet_count", 0),
                                   "listed": metrics.get("listed_count", 0)})
        except Exception as e:
            return json.dumps({"error": str(e)})
    if platform in ("instagram", "facebook"):
        token = getattr(settings, 'meta_access_token', '') or ""
        if not token:
            return json.dumps({"error": "Meta API not configured."})
        try:
            resp = await _http.get("https://graph.facebook.com/v19.0/me/accounts",
                params={"access_token": token})
            if resp.status_code == 200:
                pages = resp.json().get("data", [])
                if pages:
                    page_token = pages[0].get("access_token", "")
                    page_id = pages[0].get("id", "")
                    metrics_resp = await _http.get(
                        f"https://graph.facebook.com/v19.0/{page_id}/insights",
                        params={"access_token": page_token, "metric": "page_impressions,page_engaged_users",
                                "period": "day"})
                    if metrics_resp.status_code == 200:
                        return json.dumps({"platform": platform, "insights": metrics_resp.json().get("data", [])[:5]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Analytics not configured for {platform}"})



async def _monitor_community(platform: str, keywords: str, limit: int = 10) -> str:
    """Monitor Reddit, Hacker News, or Product Hunt for brand mentions and opportunities."""
    keyword_list = [k.strip() for k in keywords.split(",")]
    if platform == "reddit":
        try:
            results = []
            for kw in keyword_list[:3]:
                resp = await _http.get(f"https://www.reddit.com/search.json",
                    params={"q": kw, "sort": "new", "limit": min(limit, 10)},
                    headers={"User-Agent": "SupervisorBot/1.0"})
                if resp.status_code == 200:
                    posts = resp.json().get("data", {}).get("children", [])
                    for p in posts:
                        d = p.get("data", {})
                        results.append({"title": d.get("title", "")[:200],
                                        "subreddit": d.get("subreddit", ""),
                                        "url": f"https://reddit.com{d.get('permalink', '')}",
                                        "score": d.get("score", 0),
                                        "comments": d.get("num_comments", 0)})
            return json.dumps({"platform": "reddit", "keywords": keyword_list,
                               "results": results[:limit]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "hackernews":
        try:
            results = []
            for kw in keyword_list[:3]:
                resp = await _http.get("https://hn.algolia.com/api/v1/search_by_date",
                    params={"query": kw, "hitsPerPage": min(limit, 10)})
                if resp.status_code == 200:
                    hits = resp.json().get("hits", [])
                    for h in hits:
                        results.append({"title": h.get("title", "") or h.get("story_title", ""),
                                        "url": h.get("url", "") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                                        "points": h.get("points", 0),
                                        "comments": h.get("num_comments", 0)})
            return json.dumps({"platform": "hackernews", "keywords": keyword_list,
                               "results": results[:limit]})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "producthunt":
        ph_token = getattr(settings, 'producthunt_token', '') or ""
        if ph_token:
            try:
                resp = await _http.post("https://api.producthunt.com/v2/api/graphql",
                    headers={"Authorization": f"Bearer {ph_token}", "Content-Type": "application/json"},
                    json={"query": f'{{ posts(order: NEWEST, topic: "{keyword_list[0]}") {{ edges {{ node {{ name tagline url votesCount }} }} }} }}'})
                if resp.status_code == 200:
                    edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
                    results = [{"name": e["node"]["name"], "tagline": e["node"]["tagline"],
                                "url": e["node"]["url"], "votes": e["node"]["votesCount"]}
                               for e in edges[:limit]]
                    return json.dumps({"platform": "producthunt", "results": results})
            except Exception as e:
                return json.dumps({"error": str(e)})
        return json.dumps({"error": "Product Hunt not configured. Set PRODUCTHUNT_TOKEN."})
    return json.dumps({"error": f"Unknown platform: {platform}"})



def register_social_tools(registry):
    """Register all social tools with the given registry."""
    from models import ToolParameter

    registry.register("post_twitter", "Post a tweet. Max 10 posts/day.",
        [ToolParameter(name="text", description="Tweet text (max 280 chars)"),
         ToolParameter(name="media_ids", description="Comma-separated media IDs", required=False)],
        _post_twitter, "social")

    registry.register("search_twitter", "Search Twitter for relevant conversations and engagement opportunities.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="max_results", type="integer", description="Max results (1-100)", required=False)],
        _search_twitter, "social")

    registry.register("post_linkedin", "Post to LinkedIn. Max 2 posts/day.",
        [ToolParameter(name="text", description="Post text"),
         ToolParameter(name="image_url", description="Optional image URL", required=False)],
        _post_linkedin, "social")

    registry.register("post_instagram", "Post to Instagram via Meta Graph API (Business account required).",
        [ToolParameter(name="caption", description="Post caption"),
         ToolParameter(name="image_url", description="Public image URL to post")],
        _post_instagram, "social")

    registry.register("schedule_social_post", "Schedule a social post for future publication via Buffer.",
        [ToolParameter(name="platform", description="Platform: twitter, linkedin, instagram, facebook"),
         ToolParameter(name="text", description="Post content"),
         ToolParameter(name="scheduled_time", description="ISO 8601 datetime for publishing"),
         ToolParameter(name="image_url", description="Optional image URL", required=False)],
        _schedule_social_post, "social")

    registry.register("get_social_analytics", "Get social media engagement metrics for a platform.",
        [ToolParameter(name="platform", description="Platform: twitter, instagram, facebook"),
         ToolParameter(name="period", description="Period: 7d, 30d, 90d", required=False)],
        _get_social_analytics, "social")

    registry.register("monitor_community", "Monitor Reddit, Hacker News, or Product Hunt for mentions and opportunities.",
        [ToolParameter(name="platform", description="Platform: reddit, hackernews, producthunt"),
         ToolParameter(name="keywords", description="Comma-separated keywords to monitor"),
         ToolParameter(name="limit", type="integer", description="Max results", required=False)],
        _monitor_community, "social")

    # ── SEO & Content Tools ──

