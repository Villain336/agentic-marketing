"""
SEO keyword research, backlink analysis, image generation, CMS publishing, and plagiarism checking.
"""

from __future__ import annotations

import json
import re
import base64

from config import settings
from tools.registry import _http, _http_long


def _get_web_search():
    from tools.research import _web_search
    return _web_search
async def _seo_keyword_research(keyword: str, country: str = "us") -> str:
    """Get keyword difficulty, search volume, CPC via DataForSEO or SEMrush."""
    dataforseo_login = getattr(settings, 'dataforseo_login', '') or ""
    dataforseo_pass = getattr(settings, 'dataforseo_password', '') or ""
    if dataforseo_login and dataforseo_pass:
        try:
            auth = base64.b64encode(f"{dataforseo_login}:{dataforseo_pass}".encode()).decode()
            resp = await _http.post("https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"keywords": [keyword], "location_code": 2840 if country == "us" else 2826,
                       "language_code": "en"}])
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("tasks", [{}])[0].get("result", [])
                if results:
                    r = results[0]
                    return json.dumps({
                        "keyword": keyword, "search_volume": r.get("search_volume", 0),
                        "cpc": r.get("cpc", 0), "competition": r.get("competition", ""),
                        "competition_index": r.get("competition_index", 0),
                    })
        except Exception as e:
            return json.dumps({"keyword": keyword, "error": str(e)})
    semrush_key = getattr(settings, 'semrush_api_key', '') or ""
    if semrush_key:
        try:
            resp = await _http.get("https://api.semrush.com/",
                params={"type": "phrase_this", "key": semrush_key, "phrase": keyword,
                        "database": country, "export_columns": "Ph,Nq,Cp,Co,Nr"})
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                if len(lines) >= 2:
                    vals = lines[1].split(";")
                    return json.dumps({
                        "keyword": keyword, "search_volume": int(vals[1]) if len(vals) > 1 else 0,
                        "cpc": float(vals[2]) if len(vals) > 2 else 0,
                        "competition": float(vals[3]) if len(vals) > 3 else 0,
                    })
        except Exception as e:
            return json.dumps({"keyword": keyword, "error": str(e)})
    return await _get_web_search()(f"{keyword} search volume CPC keyword difficulty", 3)



async def _seo_backlink_analysis(domain: str) -> str:
    """Analyze backlink profile via DataForSEO or Ahrefs."""
    dataforseo_login = getattr(settings, 'dataforseo_login', '') or ""
    dataforseo_pass = getattr(settings, 'dataforseo_password', '') or ""
    if dataforseo_login and dataforseo_pass:
        try:
            auth = base64.b64encode(f"{dataforseo_login}:{dataforseo_pass}".encode()).decode()
            resp = await _http.post("https://api.dataforseo.com/v3/backlinks/summary/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"target": domain}])
            if resp.status_code == 200:
                data = resp.json()
                r = data.get("tasks", [{}])[0].get("result", [{}])[0]
                return json.dumps({
                    "domain": domain,
                    "backlinks_total": r.get("backlinks", 0),
                    "referring_domains": r.get("referring_domains", 0),
                    "domain_rank": r.get("rank", 0),
                    "dofollow": r.get("referring_links_types", {}).get("dofollow", 0),
                    "nofollow": r.get("referring_links_types", {}).get("nofollow", 0),
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return await _get_web_search()(f'site:{domain} backlinks referring domains', 3)



async def _generate_image(prompt: str, style: str = "professional",
                           size: str = "1024x1024") -> str:
    """Generate image via OpenAI DALL-E, Replicate Flux, or Fal.ai."""
    openai_key = getattr(settings, 'openai_image_key', '') or ""
    if not openai_key:
        for p in settings.providers:
            if p.name == "openai" and p.api_key:
                openai_key = p.api_key
                break
    if openai_key:
        try:
            resp = await _http_long.post("https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "dall-e-3", "prompt": f"{style} style: {prompt}",
                      "n": 1, "size": size, "quality": "standard"})
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("data", [{}])[0].get("url", "")
                revised = data.get("data", [{}])[0].get("revised_prompt", "")
                return json.dumps({"image_url": url, "revised_prompt": revised, "provider": "dall-e-3"})
            return json.dumps({"error": f"OpenAI {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "dall-e-3"})
    replicate_key = getattr(settings, 'replicate_api_key', '') or ""
    if replicate_key:
        try:
            resp = await _http_long.post("https://api.replicate.com/v1/predictions",
                headers={"Authorization": f"Bearer {replicate_key}", "Content-Type": "application/json"},
                json={"version": "black-forest-labs/flux-1.1-pro",
                      "input": {"prompt": f"{style} style: {prompt}",
                                "width": int(size.split("x")[0]),
                                "height": int(size.split("x")[1])}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"prediction_id": data.get("id", ""), "status": data.get("status", ""),
                                   "provider": "replicate/flux"})
            return json.dumps({"error": f"Replicate {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "replicate"})
    fal_key = getattr(settings, 'fal_api_key', '') or ""
    if fal_key:
        try:
            resp = await _http_long.post("https://queue.fal.run/fal-ai/flux/dev",
                headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                json={"prompt": f"{style} style: {prompt}",
                      "image_size": {"width": int(size.split("x")[0]),
                                     "height": int(size.split("x")[1])}})
            if resp.status_code in (200, 201):
                data = resp.json()
                images = data.get("images", [])
                url = images[0].get("url", "") if images else ""
                return json.dumps({"image_url": url, "provider": "fal.ai/flux"})
            return json.dumps({"error": f"Fal.ai {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "fal.ai"})
    return json.dumps({"error": "No image generation API configured. Set OPENAI_API_KEY, REPLICATE_API_KEY, or FAL_API_KEY."})



async def _publish_to_cms(title: str, content: str, status: str = "draft",
                           platform: str = "wordpress", tags: str = "") -> str:
    """Publish content to WordPress, Ghost, or Webflow CMS."""
    if platform == "wordpress":
        wp_url = getattr(settings, 'wordpress_url', '') or ""
        wp_user = getattr(settings, 'wordpress_user', '') or ""
        wp_app_password = getattr(settings, 'wordpress_app_password', '') or ""
        if not wp_url or not wp_user:
            return json.dumps({"error": "WordPress not configured. Set WORDPRESS_URL and WORDPRESS_USER.",
                               "draft": {"title": title, "status": status}})
        try:
            auth = base64.b64encode(f"{wp_user}:{wp_app_password}".encode()).decode()
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            resp = await _http.post(f"{wp_url}/wp-json/wp/v2/posts",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json={"title": title, "content": content, "status": status,
                      "tags": tag_list})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"post_id": data.get("id", ""), "url": data.get("link", ""),
                                   "status": data.get("status", ""), "platform": "wordpress"})
            return json.dumps({"error": f"WordPress {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "ghost":
        ghost_url = getattr(settings, 'ghost_url', '') or ""
        ghost_key = getattr(settings, 'ghost_admin_key', '') or ""
        if not ghost_url or not ghost_key:
            return json.dumps({"error": "Ghost not configured. Set GHOST_URL and GHOST_ADMIN_KEY.",
                               "draft": {"title": title, "status": status}})
        try:
            import time, hashlib, hmac
            key_id, secret = ghost_key.split(":")
            iat = int(time.time())
            header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode()).decode().rstrip("=")
            payload_b = base64.urlsafe_b64encode(json.dumps({"iat": iat, "exp": iat + 300, "aud": "/admin/"}).encode()).decode().rstrip("=")
            sig_input = f"{header}.{payload_b}"
            sig = base64.urlsafe_b64encode(hmac.new(bytes.fromhex(secret), sig_input.encode(), hashlib.sha256).digest()).decode().rstrip("=")
            token = f"{sig_input}.{sig}"
            resp = await _http.post(f"{ghost_url}/ghost/api/admin/posts/",
                headers={"Authorization": f"Ghost {token}", "Content-Type": "application/json"},
                json={"posts": [{"title": title, "html": content, "status": status,
                                 "tags": [{"name": t.strip()} for t in tags.split(",")] if tags else []}]})
            if resp.status_code in (200, 201):
                data = resp.json()
                post = data.get("posts", [{}])[0]
                return json.dumps({"post_id": post.get("id", ""), "url": post.get("url", ""),
                                   "status": post.get("status", ""), "platform": "ghost"})
            return json.dumps({"error": f"Ghost {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif platform == "webflow":
        wf_key = getattr(settings, 'webflow_api_key', '') or ""
        wf_collection = getattr(settings, 'webflow_blog_collection_id', '') or ""
        if not wf_key or not wf_collection:
            return json.dumps({"error": "Webflow not configured. Set WEBFLOW_API_KEY.",
                               "draft": {"title": title, "status": status}})
        try:
            resp = await _http.post(f"https://api.webflow.com/v2/collections/{wf_collection}/items",
                headers={"Authorization": f"Bearer {wf_key}", "Content-Type": "application/json"},
                json={"fieldData": {"name": title, "post-body": content, "slug": re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-'))}})
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                return json.dumps({"item_id": data.get("id", ""), "status": "draft", "platform": "webflow"})
            return json.dumps({"error": f"Webflow {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown CMS platform: {platform}"})



async def _check_plagiarism(text: str) -> str:
    """Check text originality via Copyscape API."""
    copyscape_user = getattr(settings, 'copyscape_user', '') or ""
    copyscape_key = getattr(settings, 'copyscape_api_key', '') or ""
    if not copyscape_user or not copyscape_key:
        return json.dumps({"note": "Plagiarism check not configured. Set COPYSCAPE_USER and COPYSCAPE_API_KEY.",
                           "word_count": len(text.split()),
                           "recommendation": "Manually check via copyscape.com before publishing."})
    try:
        resp = await _http.post("https://www.copyscape.com/api/",
            data={"u": copyscape_user, "o": copyscape_key, "t": text[:5000], "f": "json"})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "original": data.get("result", "") == "0",
                "matches_found": int(data.get("count", 0)),
                "matches": [{"url": m.get("url", ""), "percent": m.get("percentmatched", "")}
                            for m in data.get("result", [])[:5]] if isinstance(data.get("result"), list) else [],
            })
        return json.dumps({"error": f"Copyscape {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_content_tools(registry):
    """Register all content tools with the given registry."""
    from models import ToolParameter

    registry.register("seo_keyword_research", "Get keyword difficulty, search volume, CPC via DataForSEO or SEMrush.",
        [ToolParameter(name="keyword", description="Keyword to research"),
         ToolParameter(name="country", description="Country code (default: us)", required=False)],
        _seo_keyword_research, "seo")

    registry.register("seo_backlink_analysis", "Analyze backlink profile for a domain.",
        [ToolParameter(name="domain", description="Domain to analyze")],
        _seo_backlink_analysis, "seo")

    registry.register("generate_image", "Generate an image using DALL-E 3, Replicate Flux, or Fal.ai.",
        [ToolParameter(name="prompt", description="Detailed image description"),
         ToolParameter(name="style", description="Style: professional, minimal, bold, creative", required=False),
         ToolParameter(name="size", description="Image size: 1024x1024, 1792x1024, 1024x1792", required=False)],
        _generate_image, "content")

    registry.register("publish_to_cms", "Publish content to WordPress, Ghost, or Webflow CMS.",
        [ToolParameter(name="title", description="Post title"),
         ToolParameter(name="content", description="Post content (HTML)"),
         ToolParameter(name="status", description="Status: draft or publish", required=False),
         ToolParameter(name="platform", description="CMS: wordpress, ghost, webflow", required=False),
         ToolParameter(name="tags", description="Comma-separated tags", required=False)],
        _publish_to_cms, "content")

    registry.register("check_plagiarism", "Check text originality via Copyscape.",
        [ToolParameter(name="text", description="Text to check (up to 5000 chars)")],
        _check_plagiarism, "content")

    # ── Ad Tools ──

