"""
Reddit, Hacker News, TikTok trends, and YouTube trends.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


from tools.research import _web_search
async def _search_reddit(query: str, subreddit: str = "", sort: str = "relevance", time_filter: str = "week") -> str:
    """Search Reddit for discussions, sentiment, and trending posts."""
    try:
        sub_path = f"r/{subreddit}/" if subreddit else ""
        url = f"https://www.reddit.com/{sub_path}search.json?q={query}&sort={sort}&t={time_filter}&limit=15"
        resp = await _http.get(url, headers={"User-Agent": "SupervisorBot/1.0"})
        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("children", [])
            results = []
            for post in data[:10]:
                p = post.get("data", {})
                results.append({
                    "title": p.get("title", ""),
                    "subreddit": p.get("subreddit", ""),
                    "score": p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "created": p.get("created_utc", 0),
                    "selftext_preview": (p.get("selftext", ""))[:200],
                })
            return json.dumps({"query": query, "subreddit": subreddit or "all", "results": results, "count": len(results)})
        return json.dumps({"query": query, "results": [], "note": "Reddit API returned non-200, try web_search as fallback"})
    except Exception as e:
        return json.dumps({"query": query, "error": str(e), "fallback": "Use web_search with 'site:reddit.com' as alternative"})



async def _post_to_reddit(subreddit: str, body: str, title: str = "", post_type: str = "comment", parent_url: str = "") -> str:
    """Post to Reddit — requires OAuth. Returns draft if no credentials."""
    reddit_client_id = getattr(settings, 'reddit_client_id', '')
    reddit_client_secret = getattr(settings, 'reddit_client_secret', '')
    if reddit_client_id and reddit_client_secret:
        try:
            import base64 as _b64
            creds = _b64.b64encode(f"{reddit_client_id}:{reddit_client_secret}".encode()).decode()
            token_resp = await _http.post(
                "https://www.reddit.com/api/v1/access_token",
                headers={
                    "Authorization": f"Basic {creds}",
                    "User-Agent": "SupervisorBot/1.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content="grant_type=client_credentials",
            )
            if token_resp.status_code == 200:
                access_token = token_resp.json().get("access_token", "")
                oauth_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "SupervisorBot/1.0",
                }
                if post_type == "comment":
                    # Extract thing_id from parent_url if provided (e.g. t3_abc123)
                    thing_id = parent_url.strip().split("/")[-1] if parent_url else ""
                    post_resp = await _http.post(
                        "https://oauth.reddit.com/api/comment",
                        headers=oauth_headers,
                        data={"thing_id": thing_id, "text": body},
                    )
                else:
                    kind = "self" if post_type == "text" else "link"
                    post_data = {"kind": kind, "sr": subreddit, "title": title, "resubmit": "true"}
                    if kind == "self":
                        post_data["text"] = body
                    else:
                        post_data["url"] = body
                    post_resp = await _http.post(
                        "https://oauth.reddit.com/api/submit",
                        headers=oauth_headers,
                        data=post_data,
                    )
                result = post_resp.json()
                errors = result.get("json", {}).get("errors", [])
                if errors:
                    return json.dumps({"status": "error", "errors": errors, "subreddit": f"r/{subreddit}"})
                post_url = result.get("json", {}).get("data", {}).get("url", "")
                return json.dumps({
                    "status": "posted",
                    "subreddit": f"r/{subreddit}",
                    "post_type": post_type,
                    "url": post_url,
                    "response": result.get("json", {}).get("data", {}),
                })
            else:
                return json.dumps({
                    "status": "auth_failed",
                    "http_status": token_resp.status_code,
                    "note": "Failed to obtain Reddit access token. Check REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.",
                })
        except Exception as e:
            logger.warning(f"Reddit post failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    # Stub fallback — no credentials configured
    return json.dumps({
        "status": "draft_created",
        "subreddit": f"r/{subreddit}",
        "post_type": post_type,
        "title": title,
        "body": body,
        "parent_url": parent_url,
        "note": "Reddit posting requires OAuth token. Draft saved — configure REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to auto-post.",
        "manual_action": f"Post this to r/{subreddit} manually or configure Reddit OAuth credentials for automation.",
    })



async def _search_hackernews(query: str, type: str = "all", sort: str = "relevance") -> str:
    """Search Hacker News via Algolia API."""
    try:
        type_filter = ""
        if type == "show_hn":
            query = f"Show HN {query}"
        elif type == "ask_hn":
            query = f"Ask HN {query}"

        sort_param = "search" if sort == "relevance" else "search_by_date"
        url = f"https://hn.algolia.com/api/v1/{sort_param}?query={query}&tags=story&hitsPerPage=15"
        resp = await _http.get(url)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            results = []
            for h in hits[:10]:
                results.append({
                    "title": h.get("title", ""),
                    "url": h.get("url", ""),
                    "points": h.get("points", 0),
                    "comments": h.get("num_comments", 0),
                    "author": h.get("author", ""),
                    "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                    "created_at": h.get("created_at", ""),
                })
            return json.dumps({"query": query, "results": results, "count": len(results)})
        return json.dumps({"query": query, "results": [], "note": "HN API returned non-200"})
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})



async def _post_to_hackernews(title: str, url: str = "", text: str = "") -> str:
    """Submit to Hacker News — no public posting API exists. Returns a draft with guidance.

    Note: Hacker News does not provide a public API for submitting posts or comments.
    Automation via session cookies violates HN's Terms of Service and risks account bans.
    This function intentionally remains a stub that returns a formatted draft for manual submission.
    """
    content_type = "link" if url else "text"
    return json.dumps({
        "status": "draft_ready",
        "title": title,
        "url": url,
        "text": text,
        "content_type": content_type,
        "submit_url": "https://news.ycombinator.com/submit",
        "important_note": (
            "Hacker News has NO public posting API. Automated submission via session cookies "
            "violates HN Terms of Service and can result in permanent account suspension. "
            "This draft must be submitted manually."
        ),
        "submission_tips": [
            "Best times: weekday mornings 8-10 AM EST for maximum visibility",
            "Titles should be factual and descriptive — no marketing language or exclamation points",
            "Show HN posts must genuinely show something you built; include a brief explanation in comments",
            "Ask HN posts work best as genuine open questions to the community",
            "Avoid reposting within 30 days — HN penalizes reposts",
            "Engage authentically in comments — the community values honest discussion",
        ],
        "title_guidelines": {
            "do": ["State what the thing is clearly", "Use the original article title when sharing news", "Be specific"],
            "dont": ["Use clickbait or superlatives", "Add 'Check this out!' type phrases", "All-caps"],
        },
    })



async def _search_tiktok_trends(query: str, region: str = "us") -> str:
    """Research TikTok trends — sounds, hashtags, content formats."""
    tiktok_api_key = getattr(settings, 'tiktok_business_api_key', '')
    if tiktok_api_key:
        try:
            resp = await _http.post(
                "https://open.tiktokapis.com/v2/research/video/query/",
                headers={
                    "Authorization": f"Bearer {tiktok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": {
                        "and": [{"operation": "IN", "field_name": "keyword", "field_values": [query]}],
                    },
                    "start_date": "20240101",
                    "end_date": "20261231",
                    "max_count": 20,
                    "search_id": "",
                    "is_random": False,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                videos = data.get("videos", [])
                trend_videos = [
                    {
                        "id": v.get("id"),
                        "description": v.get("video_description", "")[:200],
                        "likes": v.get("like_count", 0),
                        "comments": v.get("comment_count", 0),
                        "shares": v.get("share_count", 0),
                        "views": v.get("view_count", 0),
                        "hashtags": v.get("hashtag_names", []),
                        "music_title": v.get("music_id", ""),
                    }
                    for v in videos[:15]
                ]
                return json.dumps({
                    "query": query,
                    "region": region,
                    "source": "tiktok_research_api",
                    "trending_videos": trend_videos,
                    "count": len(trend_videos),
                })
        except Exception as e:
            logger.warning(f"TikTok Research API failed: {e}")

    # Use _web_search to gather real trend data
    try:
        search_result_raw = await _web_search(f"TikTok trending {query} {region} hashtags sounds 2026", 8)
        search_data = json.loads(search_result_raw)
        web_results = search_data.get("results", [])
        return json.dumps({
            "query": query,
            "region": region,
            "source": "web_search",
            "search_results": web_results,
            "trend_research": {
                "recommended_hashtags": [f"#{query.replace(' ', '')}", "#fyp", "#business", "#entrepreneur", f"#{query.split()[0]}tok" if query else "#biztok"],
                "content_formats": [
                    "Day-in-the-life: Show behind the scenes of running a business",
                    "Before/After: Client transformation stories",
                    "Myth-busting: 'Things nobody tells you about [topic]'",
                    "Storytime: Founder journey moments",
                    "Tutorial: Quick how-to in 60 seconds",
                    "Trending sound + industry take: Ride viral audio with your niche spin",
                ],
                "best_practices": {
                    "hook_window": "3 seconds — lead with the most surprising/valuable part",
                    "optimal_length": "15-45 seconds for highest completion rate",
                    "posting_frequency": "1-3x daily for growth phase",
                    "best_times": "7-9 AM, 12-2 PM, 7-11 PM in target timezone",
                    "captions": "Always add captions — 85% of TikTok is watched with sound off",
                },
                "research_sources": [
                    "Check TikTok Creative Center (ads.tiktok.com/business/creativecenter) for trending hashtags and sounds",
                    "Search TikTok app directly for competitor content",
                    "Monitor @later, @hootsuite, @sproutsocial for weekly trend roundups",
                ],
            },
            "note": "Configure TIKTOK_BUSINESS_API_KEY for direct TikTok Research API access.",
        })
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})



async def _search_youtube_trends(query: str, content_type: str = "all") -> str:
    """Research YouTube trends, Shorts formats, and content gaps."""
    try:
        yt_api_key = getattr(settings, 'youtube_api_key', '')
        if yt_api_key:
            import urllib.parse
            type_param = "&videoDuration=short" if content_type == "shorts" else ""
            search_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&q={urllib.parse.quote(query)}&type=video&order=viewCount"
                f"&maxResults=10&key={yt_api_key}{type_param}"
            )
            resp = await _http.get(search_url)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                video_ids = []
                for i in items:
                    vid_id = i["id"].get("videoId", "")
                    if vid_id:
                        video_ids.append(vid_id)
                    results.append({
                        "title": i["snippet"]["title"],
                        "channel": i["snippet"]["channelTitle"],
                        "video_id": vid_id,
                        "published": i["snippet"]["publishedAt"],
                        "description": i["snippet"].get("description", "")[:150],
                    })

                # Fetch video statistics (views, likes) via follow-up call
                if video_ids:
                    stats_url = (
                        f"https://www.googleapis.com/youtube/v3/videos"
                        f"?part=statistics&id={','.join(video_ids)}&key={yt_api_key}"
                    )
                    stats_resp = await _http.get(stats_url)
                    if stats_resp.status_code == 200:
                        stats_map = {
                            v["id"]: v.get("statistics", {})
                            for v in stats_resp.json().get("items", [])
                        }
                        for r in results:
                            s = stats_map.get(r["video_id"], {})
                            r["views"] = int(s.get("viewCount", 0))
                            r["likes"] = int(s.get("likeCount", 0))
                            r["comments"] = int(s.get("commentCount", 0))

                return json.dumps({"query": query, "content_type": content_type, "results": results, "count": len(results)})

        # Stub fallback: provide structured research guidance
        return json.dumps({
            "query": query,
            "content_type": content_type,
            "shorts_strategy": {
                "format_ideas": [
                    "Quick tip in 30s — one actionable insight",
                    "Industry myth debunked — 'Stop doing X, do Y instead'",
                    "Tool demo — 60-second walkthrough of a useful tool",
                    "Data visualization — animate a surprising stat",
                    "Client win — before/after in 15 seconds",
                    "Day-in-the-life — authentic behind-the-scenes moments",
                ],
                "best_practices": {
                    "optimal_length": "30-45 seconds for Shorts",
                    "aspect_ratio": "9:16 vertical (1080x1920)",
                    "hook": "First 3 seconds must stop the scroll — start with the payoff",
                    "captions": "Always — YouTube auto-generates but custom is better",
                    "posting_frequency": "3-5 Shorts per week minimum for algorithm favor",
                    "hashtags": f"#Shorts #{query.replace(' ', '')} #business",
                    "cta": "End with 'Follow for more' or 'Full video on my channel'",
                },
                "monetization": "Shorts Fund + Ad revenue sharing (45% creator share) at 1K subscribers",
            },
            "note": "Configure YOUTUBE_API_KEY for live trend data from YouTube Data API v3.",
        })
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})



def register_community_tools(registry):
    """Register all community tools with the given registry."""
    from models import ToolParameter

    registry.register("search_reddit", "Search Reddit for trending discussions, sentiment, and relevant posts in target subreddits.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="subreddit", description="Target subreddit (e.g. 'startups', 'smallbusiness', 'SaaS')", required=False),
         ToolParameter(name="sort", description="Sort: hot, new, top, relevance", required=False),
         ToolParameter(name="time_filter", description="Time: hour, day, week, month, year, all", required=False)],
        _search_reddit, "community")

    registry.register("post_to_reddit", "Post a value-add comment or submission to a Reddit subreddit.",
        [ToolParameter(name="subreddit", description="Target subreddit name"),
         ToolParameter(name="title", description="Post title (for submissions)", required=False),
         ToolParameter(name="body", description="Post body or comment text"),
         ToolParameter(name="post_type", description="Type: submission, comment", required=False),
         ToolParameter(name="parent_url", description="URL of post to comment on (for comments)", required=False)],
        _post_to_reddit, "community")

    registry.register("search_hackernews", "Search Hacker News for trending stories, Show HN posts, and discussions.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="type", description="Type: story, show_hn, ask_hn, all", required=False),
         ToolParameter(name="sort", description="Sort: relevance, date, points", required=False)],
        _search_hackernews, "community")

    registry.register("post_to_hackernews", "Submit a story or Show HN post to Hacker News.",
        [ToolParameter(name="title", description="Post title"),
         ToolParameter(name="url", description="URL to submit (for link posts)", required=False),
         ToolParameter(name="text", description="Post body text (for text/Show HN posts)", required=False)],
        _post_to_hackernews, "community")

    registry.register("search_tiktok_trends", "Research trending TikTok sounds, hashtags, and content formats.",
        [ToolParameter(name="query", description="Topic or niche to research"),
         ToolParameter(name="region", description="Region: us, uk, global", required=False)],
        _search_tiktok_trends, "community")

    registry.register("search_youtube_trends", "Research trending YouTube topics, Shorts formats, and content gaps.",
        [ToolParameter(name="query", description="Topic or niche to research"),
         ToolParameter(name="content_type", description="Type: shorts, long_form, all", required=False)],
        _search_youtube_trends, "community")

    # ── Full-Stack Development Tools ──

