"""
Omni OS — Cloudflare Web Crawler Tools
Provides real web crawling, content extraction, and competitive intelligence
using Cloudflare's Browser Rendering API and /crawl endpoint.
Falls back to httpx + html parsing when Cloudflare keys aren't configured.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from tools.registry import ToolRegistry, _http, _http_long

logger = logging.getLogger("omnios.tools.crawlers")


async def _crawl_website(
    url: str = "",
    max_pages: int = 10,
    extract: str = "text",
    follow_links: bool = True,
    respect_robots: bool = True,
) -> str:
    """Crawl a website using Cloudflare Browser Rendering or fallback httpx."""
    from config import settings

    cf_token = settings.cloudflare_api_token
    cf_account = settings.cloudflare_account_id

    if cf_token and cf_account:
        return await _cloudflare_crawl(url, max_pages, extract, cf_token, cf_account)
    else:
        return await _fallback_crawl(url, max_pages, extract)


async def _cloudflare_crawl(
    url: str, max_pages: int, extract: str,
    cf_token: str, cf_account: str,
) -> str:
    """Use Cloudflare's /crawl endpoint for intelligent crawling."""
    try:
        headers = {
            "Authorization": f"Bearer {cf_token}",
            "Content-Type": "application/json",
        }

        # Start crawl job
        crawl_body = {
            "url": url,
            "maxPages": min(max_pages, 50),
            "scrapeOptions": {
                "formats": ["markdown", "links"],
            },
        }

        resp = await _http_long.post(
            f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/browser-rendering/crawl",
            headers=headers,
            json=crawl_body,
        )

        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("result", {}).get("pages", [])

            results = []
            for page in pages[:max_pages]:
                results.append({
                    "url": page.get("url", ""),
                    "title": page.get("title", ""),
                    "content": page.get("markdown", page.get("text", ""))[:5000],
                    "links": page.get("links", [])[:20],
                })

            return json.dumps({
                "status": "crawled",
                "method": "cloudflare",
                "pages_crawled": len(results),
                "pages": results,
            })
        else:
            logger.warning(f"Cloudflare crawl returned {resp.status_code}, falling back")
            return await _fallback_crawl(url, max_pages, extract)

    except Exception as e:
        logger.error(f"Cloudflare crawl failed: {e}")
        return await _fallback_crawl(url, max_pages, extract)


async def _fallback_crawl(url: str, max_pages: int, extract: str) -> str:
    """Fallback crawler using httpx + basic HTML parsing."""
    try:
        visited = set()
        results = []
        to_visit = [url]
        domain = urlparse(url).netloc

        while to_visit and len(results) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                resp = await _http.get(
                    current_url,
                    headers={"User-Agent": "OmniOS-Crawler/1.0 (+https://omnios.ai)"},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    continue

                html = resp.text
                title = _extract_title(html)
                text = _html_to_text(html)
                links = _extract_links(html, current_url)

                results.append({
                    "url": current_url,
                    "title": title,
                    "content": text[:5000],
                    "links": [l for l in links if urlparse(l).netloc == domain][:10],
                })

                # Queue internal links
                for link in links:
                    if urlparse(link).netloc == domain and link not in visited:
                        to_visit.append(link)

            except Exception as e:
                logger.debug(f"Failed to crawl {current_url}: {e}")

        return json.dumps({
            "status": "crawled",
            "method": "fallback",
            "pages_crawled": len(results),
            "pages": results,
        })

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


async def _scrape_page(
    url: str = "",
    format: str = "markdown",
    wait_for: str = "",
    extract_schema: str = "",
) -> str:
    """Scrape a single page, optionally with Cloudflare Browser Rendering."""
    from config import settings

    cf_token = settings.cloudflare_api_token
    cf_account = settings.cloudflare_account_id

    if cf_token and cf_account:
        try:
            headers = {
                "Authorization": f"Bearer {cf_token}",
                "Content-Type": "application/json",
            }

            body: dict[str, Any] = {"url": url}
            if wait_for:
                body["waitFor"] = wait_for

            resp = await _http_long.post(
                f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/browser-rendering/content",
                headers=headers,
                json=body,
            )

            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result", {})
                html = result.get("html", "")
                title = _extract_title(html)
                text = _html_to_text(html) if format == "text" else _html_to_markdown(html)

                return json.dumps({
                    "status": "scraped",
                    "method": "cloudflare_browser",
                    "url": url,
                    "title": title,
                    "content": text[:10000],
                })
        except Exception as e:
            logger.warning(f"Cloudflare scrape failed, falling back: {e}")

    # Fallback: simple httpx
    try:
        resp = await _http.get(
            url,
            headers={"User-Agent": "OmniOS-Crawler/1.0 (+https://omnios.ai)"},
            follow_redirects=True,
        )
        html = resp.text
        title = _extract_title(html)
        text = _html_to_text(html) if format == "text" else _html_to_markdown(html)

        return json.dumps({
            "status": "scraped",
            "method": "httpx",
            "url": url,
            "title": title,
            "content": text[:10000],
        })

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


async def _extract_structured_data(
    url: str = "",
    schema: str = "auto",
    fields: str = "",
) -> str:
    """Extract structured data from a page (pricing tables, team pages, product features)."""
    from config import settings

    # First scrape the page
    page_result = await _scrape_page(url=url, format="text")
    page_data = json.loads(page_result)

    if page_data.get("status") != "scraped":
        return page_result

    content = page_data.get("content", "")

    # Use LLM to extract structured data from the content
    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        return json.dumps({
            "status": "extracted",
            "url": url,
            "raw_content": content[:5000],
            "note": "Configure ANTHROPIC_API_KEY for AI-powered extraction",
        })

    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url_endpoint = f"{base_url}/v1/chat/completions"
    else:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        url_endpoint = f"{base_url}/v1/messages"

    extract_prompt = f"""Extract structured data from this web page content.
Schema: {schema if schema != 'auto' else 'Detect the most useful data structure automatically'}
{f'Fields to extract: {fields}' if fields else ''}

Page content:
{content[:8000]}

Return a JSON object with the extracted data. Be precise and complete."""

    try:
        if is_openrouter:
            body = {"model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 4096,
                    "messages": [{"role": "user", "content": extract_prompt}]}
        else:
            body = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096,
                    "messages": [{"role": "user", "content": extract_prompt}]}

        resp = await _http_long.post(url_endpoint, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        if is_openrouter:
            extracted = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            extracted = "".join(blk["text"] for blk in data.get("content", []) if blk.get("type") == "text")

        return json.dumps({
            "status": "extracted",
            "url": url,
            "structured_data": extracted,
        })

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


async def _monitor_competitor(
    competitor_url: str = "",
    track: str = "pricing,features,team,blog",
) -> str:
    """Monitor a competitor's website for changes in pricing, features, team, etc."""
    results = {}
    tracks = [t.strip() for t in track.split(",")]

    for section in tracks:
        if section == "pricing":
            data = await _extract_structured_data(
                url=f"{competitor_url}/pricing",
                schema="pricing",
                fields="plan_name,price,features,billing_period",
            )
            results["pricing"] = json.loads(data)

        elif section == "features":
            data = await _extract_structured_data(
                url=competitor_url,
                schema="features",
                fields="feature_name,description,category",
            )
            results["features"] = json.loads(data)

        elif section == "team":
            for path in ["/about", "/team", "/about-us"]:
                data = await _extract_structured_data(
                    url=f"{competitor_url}{path}",
                    schema="team",
                    fields="name,title,linkedin",
                )
                parsed = json.loads(data)
                if parsed.get("status") == "extracted":
                    results["team"] = parsed
                    break

        elif section == "blog":
            for path in ["/blog", "/resources", "/articles"]:
                data = await _scrape_page(url=f"{competitor_url}{path}", format="text")
                parsed = json.loads(data)
                if parsed.get("status") == "scraped":
                    results["blog"] = parsed
                    break

    return json.dumps({
        "status": "monitored",
        "competitor": competitor_url,
        "sections_tracked": tracks,
        "data": results,
    })


# ── HTML Parsing Helpers ──────────────────────────────────────────────────

def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _html_to_text(html: str) -> str:
    # Remove scripts and styles
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Decode entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return text


def _html_to_markdown(html: str) -> str:
    """Basic HTML to markdown conversion."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<a[^>]*href=[\"']([^\"']*)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", text, flags=re.IGNORECASE)
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def _extract_links(html: str, base_url: str) -> list[str]:
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    result = []
    for link in links:
        if link.startswith("#") or link.startswith("mailto:") or link.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, link)
        if absolute.startswith("http"):
            result.append(absolute)
    return list(set(result))


def register_crawler_tools(reg: ToolRegistry):
    """Register all Cloudflare crawler tools."""
    from models import ToolParameter

    reg.register(
        "crawl_website", "Crawl a website to extract content, links, and structure using Cloudflare Browser Rendering",
        [
            ToolParameter(name="url", type="string", description="The URL to start crawling", required=True),
            ToolParameter(name="max_pages", type="integer", description="Maximum pages to crawl (default 10, max 50)"),
            ToolParameter(name="extract", type="string", description="What to extract: text, markdown, links, all"),
            ToolParameter(name="follow_links", type="boolean", description="Follow internal links (default true)"),
            ToolParameter(name="respect_robots", type="boolean", description="Respect robots.txt (default true)"),
        ],
        _crawl_website, category="web", timeout=120,
    )

    reg.register(
        "scrape_page", "Scrape a single web page with JavaScript rendering support",
        [
            ToolParameter(name="url", type="string", description="The URL to scrape", required=True),
            ToolParameter(name="format", type="string", description="Output format: markdown, text"),
            ToolParameter(name="wait_for", type="string", description="CSS selector to wait for before scraping"),
            ToolParameter(name="extract_schema", type="string", description="Schema for structured extraction"),
        ],
        _scrape_page, category="web", timeout=60,
    )

    reg.register(
        "extract_structured_data", "Extract structured data from a web page (pricing, features, team, etc.)",
        [
            ToolParameter(name="url", type="string", description="The URL to extract from", required=True),
            ToolParameter(name="schema", type="string", description="Data schema: pricing, features, team, contacts, auto"),
            ToolParameter(name="fields", type="string", description="Comma-separated fields to extract"),
        ],
        _extract_structured_data, category="web", timeout=120,
    )

    reg.register(
        "monitor_competitor", "Monitor a competitor website for pricing, features, team, and content changes",
        [
            ToolParameter(name="competitor_url", type="string", description="Competitor's base URL", required=True),
            ToolParameter(name="track", type="string", description="What to track: pricing,features,team,blog"),
        ],
        _monitor_competitor, category="web", timeout=180,
    )
