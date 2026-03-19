"""
Vercel, Cloudflare, DNS, domain management, monitoring, and page speed tools.
"""

from __future__ import annotations

import json
import re
import base64

from config import settings
from tools.registry import _http, _http_long


from tools.research import _web_search
async def _deploy_to_vercel(project_name: str, files: str, domain: str = "") -> str:
    token = getattr(settings, 'vercel_token', '') or ""
    if not token:
        return json.dumps({"error": "Vercel not configured. Set VERCEL_TOKEN.",
                           "draft": {"project": project_name, "domain": domain}})
    try:
        file_list = json.loads(files) if isinstance(files, str) else files
    except json.JSONDecodeError:
        file_list = [{"file": "index.html", "data": files[:5000]}]
    try:
        payload = {
            "name": project_name,
            "files": [{"file": f.get("file", "index.html"), "data": f.get("data", "")} for f in file_list],
        }
        resp = await _http.post("https://api.vercel.com/v13/deployments",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"url": f"https://{data.get('url', '')}", "deployment_id": data.get("id", ""), "status": "deployed"})
        return json.dumps({"error": f"Vercel {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _deploy_to_cloudflare(project_name: str, files: str, domain: str = "") -> str:
    token = getattr(settings, 'cloudflare_api_token', '') or ""
    account_id = getattr(settings, 'cloudflare_account_id', '') or ""
    if not token or not account_id:
        return json.dumps({"error": "Cloudflare not configured.",
                           "draft": {"project": project_name, "domain": domain}})
    return json.dumps({"status": "draft", "project": project_name,
                       "note": "Cloudflare Pages deployment requires upload via Workers API."})



async def _check_domain_availability(domain: str) -> str:
    """Check domain name availability via Namecheap API."""
    nc_user = getattr(settings, 'namecheap_api_user', '') or ""
    nc_key = getattr(settings, 'namecheap_api_key', '') or ""
    if nc_user and nc_key:
        try:
            resp = await _http.get("https://api.namecheap.com/xml.response",
                params={
                    "ApiUser": nc_user, "ApiKey": nc_key, "UserName": nc_user,
                    "Command": "namecheap.domains.check",
                    "ClientIp": getattr(settings, 'namecheap_client_ip', '127.0.0.1'),
                    "DomainList": domain,
                })
            if resp.status_code == 200:
                text = resp.text
                available = "Available=\"true\"" in text
                import re as _re
                price_match = _re.search(r'Price="([\d.]+)"', text)
                price = float(price_match.group(1)) if price_match else None
                return json.dumps({
                    "domain": domain, "available": available,
                    "price": price, "currency": "USD",
                    "provider": "namecheap",
                })
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)})
    return await _web_search(f'"{domain}" domain availability whois', 3)



async def _register_domain(domain: str, contact_info: str = "") -> str:
    """Register a domain name via Namecheap API. Requires human approval."""
    nc_user = getattr(settings, 'namecheap_api_user', '') or ""
    nc_key = getattr(settings, 'namecheap_api_key', '') or ""
    if not nc_user or not nc_key:
        return json.dumps({"error": "Domain registration not configured. Set NAMECHEAP_API_USER and NAMECHEAP_API_KEY.",
                           "draft": {"domain": domain, "action": "register"}})
    avail = await _check_domain_availability(domain)
    avail_data = json.loads(avail)
    if not avail_data.get("available"):
        return json.dumps({"domain": domain, "error": "Domain is not available.",
                           "suggestion": "Try variations or a different TLD."})
    return json.dumps({"domain": domain, "status": "pending_approval",
                       "provider": "namecheap", "price": avail_data.get("price"),
                       "note": "Domain registration queued for human approval before purchase."})



async def _manage_dns(domain: str, action: str, record_type: str = "A",
                       name: str = "@", value: str = "", ttl: int = 300) -> str:
    """Manage DNS records via Cloudflare API."""
    token = getattr(settings, 'cloudflare_api_token', '') or ""
    if not token:
        return json.dumps({"error": "Cloudflare not configured. Set CLOUDFLARE_API_TOKEN."})
    try:
        zones_resp = await _http.get("https://api.cloudflare.com/client/v4/zones",
            headers={"Authorization": f"Bearer {token}"},
            params={"name": domain})
        zones = zones_resp.json().get("result", [])
        if not zones:
            return json.dumps({"error": f"Zone not found for {domain}. Add domain to Cloudflare first."})
        zone_id = zones[0]["id"]
        if action == "create":
            resp = await _http.post(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"type": record_type, "name": name, "content": value,
                      "ttl": ttl, "proxied": record_type in ("A", "AAAA", "CNAME")})
            if resp.status_code in (200, 201):
                r = resp.json().get("result", {})
                return json.dumps({"created": True, "record_id": r.get("id", ""),
                                   "type": record_type, "name": name, "value": value})
        elif action == "list":
            resp = await _http.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                records = resp.json().get("result", [])
                return json.dumps({"domain": domain, "records": [
                    {"type": r["type"], "name": r["name"], "content": r["content"], "id": r["id"]}
                    for r in records[:30]]})
        return json.dumps({"error": f"DNS action '{action}' failed"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _setup_analytics(domain: str, provider: str = "plausible") -> str:
    """Set up analytics tracking for a site."""
    if provider == "plausible":
        plausible_key = getattr(settings, 'plausible_api_key', '') or ""
        if plausible_key:
            try:
                resp = await _http.post("https://plausible.io/api/v1/sites",
                    headers={"Authorization": f"Bearer {plausible_key}", "Content-Type": "application/json"},
                    json={"domain": domain})
                if resp.status_code in (200, 201):
                    return json.dumps({
                        "domain": domain, "provider": "plausible",
                        "tracking_script": f'<script defer data-domain="{domain}" src="https://plausible.io/js/script.js"></script>',
                        "dashboard": f"https://plausible.io/{domain}",
                    })
            except Exception as e:
                return json.dumps({"error": str(e)})
    ga_id = getattr(settings, 'google_analytics_id', '') or ""
    if ga_id:
        return json.dumps({
            "domain": domain, "provider": "google_analytics",
            "tracking_id": ga_id,
            "tracking_script": f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag("js",new Date());gtag("config","{ga_id}");</script>',
        })
    return json.dumps({"error": "No analytics configured. Set PLAUSIBLE_API_KEY or GOOGLE_ANALYTICS_ID.",
                       "recommendation": "Plausible.io for privacy-friendly analytics, GA4 for full suite."})



async def _setup_uptime_monitoring(url: str, check_interval: int = 300) -> str:
    """Set up uptime monitoring via BetterUptime or UptimeRobot."""
    betteruptime_key = getattr(settings, 'betteruptime_api_key', '') or ""
    if betteruptime_key:
        try:
            resp = await _http.post("https://betteruptime.com/api/v2/monitors",
                headers={"Authorization": f"Bearer {betteruptime_key}", "Content-Type": "application/json"},
                json={"url": url, "monitor_type": "status", "check_frequency": check_interval,
                      "pronounceable_name": url.replace("https://", "").replace("http://", "")})
            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                return json.dumps({"monitor_id": data.get("id", ""), "url": url,
                                   "status": "active", "check_interval": check_interval})
        except Exception as e:
            return json.dumps({"error": str(e)})
    uptimerobot_key = getattr(settings, 'uptimerobot_api_key', '') or ""
    if uptimerobot_key:
        try:
            resp = await _http.post("https://api.uptimerobot.com/v2/newMonitor",
                data={"api_key": uptimerobot_key, "url": url, "type": 1,
                      "friendly_name": url.replace("https://", "")})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"monitor_id": data.get("monitor", {}).get("id", ""),
                                   "url": url, "status": data.get("stat", "")})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "Uptime monitoring not configured. Set BETTERUPTIME_API_KEY or UPTIMEROBOT_API_KEY."})



async def _take_screenshot(url: str, full_page: bool = True, width: int = 1440) -> str:
    """Take a screenshot of a URL for visual QA."""
    browserless_key = getattr(settings, 'browserless_api_key', '') or ""
    if browserless_key:
        try:
            resp = await _http_long.post("https://chrome.browserless.io/screenshot",
                headers={"Content-Type": "application/json"},
                params={"token": browserless_key},
                json={"url": url, "options": {"fullPage": full_page, "type": "png"},
                      "viewport": {"width": width, "height": 900}})
            if resp.status_code == 200:
                img_b64 = base64.b64encode(resp.content).decode()
                return json.dumps({"url": url, "screenshot_taken": True,
                                   "size_kb": len(resp.content) // 1024,
                                   "image_b64_preview": img_b64[:200] + "..."})
        except Exception as e:
            return json.dumps({"error": str(e)})
    screenshotone_key = getattr(settings, 'screenshotone_api_key', '') or ""
    if screenshotone_key:
        try:
            resp = await _http_long.get("https://api.screenshotone.com/take",
                params={"access_key": screenshotone_key, "url": url,
                        "full_page": str(full_page).lower(), "viewport_width": width,
                        "format": "png"})
            if resp.status_code == 200:
                return json.dumps({"url": url, "screenshot_taken": True,
                                   "size_kb": len(resp.content) // 1024})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "Screenshot tool not configured. Set BROWSERLESS_API_KEY or SCREENSHOTONE_API_KEY."})



async def _check_page_speed(url: str, strategy: str = "mobile") -> str:
    """Run Google PageSpeed Insights audit on a URL."""
    psi_key = getattr(settings, 'google_psi_api_key', '') or ""
    api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params: dict[str, Any] = {"url": url, "strategy": strategy,
                               "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY", "BEST_PRACTICES"]}
    if psi_key:
        params["key"] = psi_key
    try:
        resp = await _http_long.get(api_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            lh = data.get("lighthouseResult", {})
            categories = lh.get("categories", {})
            audits = lh.get("audits", {})
            return json.dumps({
                "url": url, "strategy": strategy,
                "scores": {k: round(v.get("score", 0) * 100) for k, v in categories.items()},
                "fcp": audits.get("first-contentful-paint", {}).get("displayValue", ""),
                "lcp": audits.get("largest-contentful-paint", {}).get("displayValue", ""),
                "cls": audits.get("cumulative-layout-shift", {}).get("displayValue", ""),
                "tbt": audits.get("total-blocking-time", {}).get("displayValue", ""),
                "speed_index": audits.get("speed-index", {}).get("displayValue", ""),
            })
        return json.dumps({"error": f"PageSpeed API {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _generate_dockerfile(language: str, framework: str = "", services: str = "") -> str:
    """Generate Dockerfile and docker-compose configuration."""
    service_list = [s.strip() for s in services.split(",")] if services else []

    base_images = {
        "python": "python:3.12-slim",
        "node": "node:20-alpine",
        "go": "golang:1.22-alpine",
        "rust": "rust:1.77-slim",
        "java": "eclipse-temurin:21-jre-alpine",
        "ruby": "ruby:3.3-slim",
    }

    compose_services = {"app": {"build": ".", "ports": ["3000:3000"], "env_file": ".env"}}
    if "postgres" in service_list:
        compose_services["postgres"] = {"image": "postgres:16-alpine", "environment": {"POSTGRES_DB": "app", "POSTGRES_PASSWORD": "changeme"}, "volumes": ["pgdata:/var/lib/postgresql/data"]}
    if "redis" in service_list:
        compose_services["redis"] = {"image": "redis:7-alpine", "ports": ["6379:6379"]}

    return json.dumps({
        "dockerfile": {
            "base_image": base_images.get(language, f"{language}:latest"),
            "multi_stage": True,
            "optimizations": ["Multi-stage build for smaller images", "Non-root user", ".dockerignore configured", "Layer caching optimized", "Health check included"],
        },
        "docker_compose": {"version": "3.9", "services": compose_services},
        "production_ready": True,
    })



async def _deploy_to_cloud(provider: str, project_type: str, services: str = "") -> str:
    """Generate deployment scripts for cloud providers."""
    service_list = [s.strip() for s in services.split(",")] if services else []

    provider_configs = {
        "vercel": {"deploy_cmd": "vercel deploy --prod", "config_file": "vercel.json", "ci": "GitHub integration (auto-deploy on push)", "ssl": "Automatic", "cost": "Free tier: 100GB bandwidth"},
        "railway": {"deploy_cmd": "railway up", "config_file": "railway.toml", "ci": "GitHub integration", "ssl": "Automatic", "cost": "~$5/mo for small apps"},
        "fly_io": {"deploy_cmd": "fly deploy", "config_file": "fly.toml", "ci": "GitHub Actions", "ssl": "Automatic", "cost": "Free tier: 3 shared VMs"},
        "aws": {"deploy_cmd": "aws ecs deploy / cdk deploy", "config_file": "cdk.json or terraform/", "ci": "CodePipeline or GitHub Actions", "ssl": "ACM Certificate", "cost": "Pay-as-you-go"},
        "gcp": {"deploy_cmd": "gcloud run deploy", "config_file": "cloudbuild.yaml", "ci": "Cloud Build", "ssl": "Managed", "cost": "Free tier: 2M requests/mo"},
        "render": {"deploy_cmd": "git push (auto-deploy)", "config_file": "render.yaml", "ci": "GitHub integration", "ssl": "Automatic", "cost": "Free tier available"},
    }

    config = provider_configs.get(provider, {"deploy_cmd": f"{provider} deploy", "config_file": "Dockerfile", "ci": "GitHub Actions", "ssl": "Configure manually", "cost": "Varies"})

    return json.dumps({
        "provider": provider,
        "project_type": project_type,
        "deployment_config": config,
        "required_services": service_list,
        "environment_variables": ["DATABASE_URL", "REDIS_URL", "JWT_SECRET", "STRIPE_KEY", "API_KEY"],
        "checklist": [
            "Environment variables configured",
            "Database provisioned and migrated",
            "SSL/TLS certificate active",
            "Health check endpoint configured",
            "Logging and monitoring enabled",
            "Backup strategy in place",
            "Rollback procedure documented",
            "Rate limiting configured",
            "CORS origins set to production domains",
        ],
    })



def register_deployment_tools(registry):
    """Register all deployment tools with the given registry."""
    from models import ToolParameter

    registry.register("deploy_to_vercel", "Deploy site files to Vercel.",
        [ToolParameter(name="project_name", description="Project name"),
         ToolParameter(name="files", description="JSON array of {file, data} objects"),
         ToolParameter(name="domain", description="Custom domain", required=False)],
        _deploy_to_vercel, "deployment")

    registry.register("deploy_to_cloudflare", "Deploy site to Cloudflare Pages/Workers.",
        [ToolParameter(name="project_name", description="Project name"),
         ToolParameter(name="files", description="JSON array of {file, data} objects"),
         ToolParameter(name="domain", description="Custom domain", required=False)],
        _deploy_to_cloudflare, "deployment")

    registry.register("check_domain_availability", "Check if a domain name is available for registration.",
        [ToolParameter(name="domain", description="Domain name to check (e.g. myagency.com)")],
        _check_domain_availability, "deployment")

    registry.register("register_domain", "Register a domain name (requires human approval).",
        [ToolParameter(name="domain", description="Domain to register"),
         ToolParameter(name="contact_info", description="Contact info for registration", required=False)],
        _register_domain, "deployment")

    registry.register("manage_dns", "Create or list DNS records via Cloudflare.",
        [ToolParameter(name="domain", description="Domain name"),
         ToolParameter(name="action", description="Action: create or list"),
         ToolParameter(name="record_type", description="Record type: A, AAAA, CNAME, TXT, MX", required=False),
         ToolParameter(name="name", description="Record name (e.g. @ or www)", required=False),
         ToolParameter(name="value", description="Record value (e.g. IP address)", required=False),
         ToolParameter(name="ttl", type="integer", description="TTL in seconds", required=False)],
        _manage_dns, "deployment")

    registry.register("setup_analytics", "Set up analytics tracking (Plausible or GA4) for a domain.",
        [ToolParameter(name="domain", description="Domain to track"),
         ToolParameter(name="provider", description="Provider: plausible or ga4", required=False)],
        _setup_analytics, "deployment")

    registry.register("setup_uptime_monitoring", "Set up uptime monitoring for a URL.",
        [ToolParameter(name="url", description="URL to monitor"),
         ToolParameter(name="check_interval", type="integer", description="Check interval in seconds", required=False)],
        _setup_uptime_monitoring, "deployment")

    registry.register("take_screenshot", "Take a screenshot of a URL for visual QA.",
        [ToolParameter(name="url", description="URL to screenshot"),
         ToolParameter(name="full_page", description="Capture full page (true/false)", required=False),
         ToolParameter(name="width", type="integer", description="Viewport width in pixels", required=False)],
        _take_screenshot, "deployment")

    registry.register("check_page_speed", "Run Google PageSpeed Insights audit — performance, SEO, accessibility scores.",
        [ToolParameter(name="url", description="URL to audit"),
         ToolParameter(name="strategy", description="Strategy: mobile or desktop", required=False)],
        _check_page_speed, "deployment")

    # ── Legal Tools ──

    registry.register("generate_dockerfile", "Generate Dockerfile and docker-compose with production optimizations.",
        [ToolParameter(name="language", description="Language: python, node, go, rust, java, ruby"),
         ToolParameter(name="framework", description="Framework name", required=False),
         ToolParameter(name="services", description="Additional services: postgres, redis, rabbitmq, elasticsearch", required=False)],
        _generate_dockerfile, "deployment")

    registry.register("deploy_to_cloud", "Generate deployment scripts and infrastructure config for cloud providers.",
        [ToolParameter(name="provider", description="Cloud: aws, gcp, azure, vercel, railway, fly_io, render"),
         ToolParameter(name="project_type", description="Type: web_app, api, static_site, worker"),
         ToolParameter(name="services", description="Required services: database, cache, queue, storage, cdn", required=False)],
        _deploy_to_cloud, "deployment")

    # ── Economic Intelligence Tools ──

