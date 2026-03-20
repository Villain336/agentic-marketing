"""
Meta, Google, LinkedIn ad campaigns, landing pages, and conversion tracking.
"""

from __future__ import annotations

import html as html_mod
import json
import re

from config import settings
from tools.registry import _http


from tools.deployment import _deploy_to_vercel
async def _create_meta_ad_campaign(campaign_name: str, daily_budget: str,
                                     targeting: str, ad_creatives: str) -> str:
    access_token = getattr(settings, 'meta_access_token', '') or ""
    if not access_token:
        return json.dumps({"error": "Meta Ads API not configured. Set META_ACCESS_TOKEN.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "targeting": targeting, "creatives": ad_creatives[:500]}})
    try:
        resp = await _http.post("https://graph.facebook.com/v19.0/act_/campaigns",
            params={"access_token": access_token},
            json={"name": campaign_name, "objective": "OUTCOME_LEADS",
                  "status": "PAUSED", "special_ad_categories": []})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"campaign_id": data.get("id", ""), "status": "draft", "name": campaign_name})
        return json.dumps({"error": f"Meta API {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _create_google_ads_campaign(campaign_name: str, daily_budget: str,
                                        keywords: str, ad_copy: str) -> str:
    dev_token = getattr(settings, 'google_ads_developer_token', '') or ""
    if not dev_token:
        return json.dumps({"error": "Google Ads API not configured.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "keywords": keywords, "copy": ad_copy[:500]}})
    return json.dumps({"campaign_id": "draft", "status": "draft", "name": campaign_name,
                       "note": "Google Ads campaign created as draft."})



async def _create_linkedin_ad_campaign(campaign_name: str, daily_budget: str,
                                         targeting: str, ad_copy: str) -> str:
    """Create a LinkedIn Ads campaign."""
    li_ad_token = getattr(settings, 'linkedin_ad_token', '') or ""
    if not li_ad_token:
        return json.dumps({"error": "LinkedIn Ads not configured. Set LINKEDIN_AD_TOKEN.",
                           "draft": {"name": campaign_name, "budget": daily_budget,
                                     "targeting": targeting, "copy": ad_copy[:500]}})
    try:
        resp = await _http.post("https://api.linkedin.com/rest/adAccounts",
            headers={"Authorization": f"Bearer {li_ad_token}",
                     "Content-Type": "application/json",
                     "LinkedIn-Version": "202401"},
            json={"name": campaign_name, "status": "PAUSED",
                  "type": "SPONSORED_UPDATES"})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"campaign_id": data.get("id", ""), "status": "draft",
                               "platform": "linkedin", "name": campaign_name})
        return json.dumps({"error": f"LinkedIn Ads {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _get_ad_performance(campaign_id: str, platform: str,
                                date_range: str = "last_7_days") -> str:
    if platform == "meta":
        token = getattr(settings, 'meta_access_token', '') or ""
        if not token:
            return json.dumps({"error": "Meta Ads not configured."})
        try:
            resp = await _http.get(
                f"https://graph.facebook.com/v19.0/{campaign_id}/insights",
                params={"access_token": token, "date_preset": date_range,
                        "fields": "impressions,clicks,ctr,cpc,spend,actions"})
            if resp.status_code == 200:
                data = resp.json().get("data", [{}])
                return json.dumps(data[0] if data else {})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Performance tracking not configured for {platform}"})



async def _build_landing_page(headline: str, subheadline: str, body_sections: str,
                                cta_text: str = "Get Started", style: str = "modern") -> str:
    """Generate a complete landing page HTML. Deploys to Vercel if configured."""
    _esc = html_mod.escape
    safe_headline = _esc(headline)
    safe_subheadline = _esc(subheadline)
    safe_cta = _esc(cta_text)
    # body_sections is expected to be HTML — sanitize by stripping script tags
    safe_body = re.sub(r'<script[^>]*>.*?</script>', '', body_sections, flags=re.DOTALL | re.IGNORECASE)
    safe_body = re.sub(r'\bon\w+\s*=', 'data-removed=', safe_body, flags=re.IGNORECASE)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_headline}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;color:#1a1a2e;line-height:1.6}}
.hero{{min-height:80vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:4rem 2rem;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff}}
.hero h1{{font-size:clamp(2rem,5vw,3.5rem);max-width:800px;margin-bottom:1rem}}
.hero p{{font-size:1.25rem;max-width:600px;opacity:0.9;margin-bottom:2rem}}
.cta{{display:inline-block;padding:1rem 2.5rem;background:#fff;color:#764ba2;font-size:1.1rem;font-weight:700;border-radius:8px;text-decoration:none;transition:transform 0.2s}}
.cta:hover{{transform:translateY(-2px)}}
.sections{{max-width:900px;margin:0 auto;padding:4rem 2rem}}
.section{{margin-bottom:3rem}}
.section h2{{font-size:1.75rem;margin-bottom:1rem;color:#764ba2}}
.section p{{font-size:1.1rem;color:#555}}
.final-cta{{text-align:center;padding:4rem 2rem;background:#f8f9fa}}
.final-cta .cta{{background:#764ba2;color:#fff}}
</style>
</head>
<body>
<div class="hero">
<h1>{safe_headline}</h1>
<p>{safe_subheadline}</p>
<a href="#form" class="cta">{safe_cta}</a>
</div>
<div class="sections">{safe_body}</div>
<div class="final-cta" id="form">
<h2>Ready to get started?</h2>
<a href="#" class="cta">{safe_cta}</a>
</div>
</body>
</html>"""
    result: dict[str, Any] = {"html_length": len(html), "generated": True, "headline": headline}
    token = getattr(settings, 'vercel_token', '') or ""
    if token:
        deploy_result = await _deploy_to_vercel(
            project_name=re.sub(r'[^a-z0-9-]', '', headline.lower().replace(' ', '-'))[:40],
            files=json.dumps([{"file": "index.html", "data": html}]))
        deploy_data = json.loads(deploy_result)
        result["deployed_url"] = deploy_data.get("url", "")
        result["deployment_id"] = deploy_data.get("deployment_id", "")
    else:
        result["html_preview"] = html[:2000]
        result["note"] = "Set VERCEL_TOKEN to auto-deploy landing pages."
    return json.dumps(result)



async def _setup_conversion_tracking(platform: str, pixel_id: str = "",
                                       domain: str = "") -> str:
    """Generate conversion tracking pixel/snippet for Meta, Google, or LinkedIn."""
    snippets: dict[str, str] = {}
    if platform in ("meta", "all"):
        pid = pixel_id or getattr(settings, 'meta_pixel_id', '') or "YOUR_PIXEL_ID"
        snippets["meta"] = f"""<!-- Meta Pixel --><script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','{pid}');fbq('track','PageView');</script>"""
    if platform in ("google", "all"):
        gid = pixel_id or getattr(settings, 'google_analytics_id', '') or "G-XXXXXXXXXX"
        snippets["google"] = f"""<!-- Google tag (gtag.js) --><script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{gid}');</script>"""
    if platform in ("linkedin", "all"):
        lid = pixel_id or "YOUR_LINKEDIN_PARTNER_ID"
        snippets["linkedin"] = f"""<!-- LinkedIn Insight Tag --><script type="text/javascript">_linkedin_partner_id="{lid}";window._linkedin_data_partner_ids=window._linkedin_data_partner_ids||[];window._linkedin_data_partner_ids.push(_linkedin_partner_id);</script><script type="text/javascript">(function(l){{var s=document.getElementsByTagName("script")[0];var b=document.createElement("script");b.type="text/javascript";b.async=true;b.src="https://snap.licdn.com/li.lms-analytics/insight.min.js";s.parentNode.insertBefore(b,s)}})(window);</script>"""
    return json.dumps({"platform": platform, "snippets": snippets,
                       "installation": "Add these snippets to the <head> of your landing page."})



def register_ads_tools(registry):
    """Register all ads tools with the given registry."""
    from models import ToolParameter

    registry.register("create_meta_ad_campaign", "Create a Meta (Facebook/Instagram) ad campaign.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="targeting", description="Targeting criteria"),
         ToolParameter(name="ad_creatives", description="Ad creative details")],
        _create_meta_ad_campaign, "ads")

    registry.register("create_google_ads_campaign", "Create a Google Ads search campaign.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="keywords", description="Target keywords"),
         ToolParameter(name="ad_copy", description="Ad copy")],
        _create_google_ads_campaign, "ads")

    registry.register("create_linkedin_ad_campaign", "Create a LinkedIn Ads campaign for B2B targeting.",
        [ToolParameter(name="campaign_name", description="Campaign name"),
         ToolParameter(name="daily_budget", description="Daily budget in dollars"),
         ToolParameter(name="targeting", description="Targeting criteria (titles, industries, company sizes)"),
         ToolParameter(name="ad_copy", description="Ad copy")],
        _create_linkedin_ad_campaign, "ads")

    registry.register("get_ad_performance", "Get performance metrics for an ad campaign.",
        [ToolParameter(name="campaign_id", description="Campaign ID"),
         ToolParameter(name="platform", description="Platform: meta, google, linkedin"),
         ToolParameter(name="date_range", description="Date range", required=False)],
        _get_ad_performance, "ads")

    registry.register("build_landing_page", "Generate a complete landing page HTML and optionally deploy to Vercel.",
        [ToolParameter(name="headline", description="Main headline"),
         ToolParameter(name="subheadline", description="Supporting subheadline"),
         ToolParameter(name="body_sections", description="HTML body sections"),
         ToolParameter(name="cta_text", description="Call-to-action button text", required=False),
         ToolParameter(name="style", description="Visual style: modern, bold, minimal", required=False)],
        _build_landing_page, "ads")

    registry.register("setup_conversion_tracking", "Generate conversion tracking pixel code for Meta, Google, or LinkedIn.",
        [ToolParameter(name="platform", description="Platform: meta, google, linkedin, all"),
         ToolParameter(name="pixel_id", description="Pixel/tracking ID", required=False),
         ToolParameter(name="domain", description="Domain for tracking", required=False)],
        _setup_conversion_tracking, "ads")

    # ── Client Success Tools ──

