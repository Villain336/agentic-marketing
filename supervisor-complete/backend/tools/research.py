"""
Web search, scraping, company research, market data, knowledge engine, and world model tools.
"""

from __future__ import annotations

import json
import re

from config import settings
from tools.registry import _http


from tools.reporting import _create_survey
async def _web_search(query: str, num_results: int = 5) -> str:
    api_key = settings.serper_api_key
    if not api_key:
        return json.dumps({"note": "Web search not configured. Set SERPER_API_KEY.", "query": query, "results": []})
    try:
        resp = await _http.post("https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num_results})
        data = resp.json()
        results = [{"title": r.get("title",""), "url": r.get("link",""), "snippet": r.get("snippet","")} for r in data.get("organic", [])[:num_results]]
        return json.dumps({"query": query, "results": results})
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})



async def _web_scrape(url: str, max_chars: int = 8000) -> str:
    try:
        resp = await _http.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; SupervisorBot/1.0)"})
        text = resp.text
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return json.dumps({"url": url, "content": text[:max_chars], "truncated": len(text) > max_chars})
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)})



async def _company_research(company_name: str, domain: str = "") -> str:
    if settings.apollo_api_key:
        try:
            resp = await _http.post("https://api.apollo.io/api/v1/mixed_companies/search",
                headers={"Content-Type": "application/json"},
                json={"api_key": settings.apollo_api_key, "q_organization_name": company_name, "page": 1, "per_page": 3})
            data = resp.json()
            results = [{
                "name": o.get("name",""), "domain": o.get("primary_domain",""),
                "industry": o.get("industry",""), "employees": o.get("estimated_num_employees",""),
                "revenue": o.get("annual_revenue_printed",""), "description": o.get("short_description","")[:300],
                "linkedin": o.get("linkedin_url",""), "location": o.get("raw_address",""),
            } for o in data.get("organizations", [])[:3]]
            return json.dumps({"company": company_name, "results": results})
        except Exception as e:
            return json.dumps({"company": company_name, "error": str(e)})
    return await _web_search(f"{company_name} company {domain} about")



async def _analyze_website(url: str) -> str:
    content = await _web_scrape(url, max_chars=5000)
    data = json.loads(content)
    if "error" in data:
        return content
    text = data.get("content", "")
    return json.dumps({"url": url, "word_count": len(text.split()), "has_content": len(text.split()) > 100, "excerpt": text[:2000]})



async def _get_market_data(symbols: str, timeframe: str = "1d") -> str:
    """Get market data for specified symbols."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")]

    try:
        # Try Alpha Vantage or similar free API
        results = {}
        for symbol in symbol_list[:5]:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={timeframe}&interval=1d"
                resp = await _http.get(url, headers={"User-Agent": "SupervisorBot/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    results[symbol] = {
                        "price": meta.get("regularMarketPrice", "N/A"),
                        "previous_close": meta.get("previousClose", "N/A"),
                        "currency": meta.get("currency", "USD"),
                        "exchange": meta.get("exchangeName", ""),
                    }
                else:
                    results[symbol] = {"note": "Data unavailable — use web_search for current price"}
            except Exception:
                results[symbol] = {"note": "Lookup failed — use web_search as fallback"}

        return json.dumps({
            "symbols": symbol_list,
            "timeframe": timeframe,
            "data": results,
            "note": "For comprehensive market data, configure ALPHA_VANTAGE_API_KEY or POLYGON_API_KEY.",
        })
    except Exception as e:
        return json.dumps({"symbols": symbol_list, "error": str(e)})



async def _track_competitor(competitor_domain: str, metrics: str = "all") -> str:
    """Track competitor changes — site content, social, traffic, tech stack."""
    results: dict[str, Any] = {"domain": competitor_domain, "tracked_at": "now"}
    site_data = await _web_scrape(f"https://{competitor_domain}", 3000)
    site = json.loads(site_data)
    if not site.get("error"):
        content = site.get("content", "")
        results["site_headline"] = content[:200]
        results["word_count"] = len(content.split())
    builtwith_key = getattr(settings, 'builtwith_api_key', '') or ""
    if builtwith_key:
        try:
            resp = await _http.get(f"https://api.builtwith.com/v21/api.json",
                params={"KEY": builtwith_key, "LOOKUP": competitor_domain})
            if resp.status_code == 200:
                data = resp.json()
                techs = []
                for group in data.get("Results", [{}])[0].get("Result", {}).get("Paths", [{}])[0].get("Technologies", []):
                    techs.append({"name": group.get("Name", ""), "category": group.get("Tag", "")})
                results["tech_stack"] = techs[:20]
        except Exception as e:
            results["tech_error"] = str(e)
    social_search = await _web_search(f'site:linkedin.com "{competitor_domain}"', 3)
    results["linkedin_presence"] = json.loads(social_search).get("results", [])[:2]
    return json.dumps(results)



async def _run_market_survey(topic: str, audience: str, questions_count: int = 5) -> str:
    """Generate a market research survey and create it via Typeform if available."""
    survey_questions = [
        {"title": f"How do you currently handle {topic}?", "type": "long_text"},
        {"title": f"What's your biggest frustration with existing {topic} solutions?", "type": "long_text"},
        {"title": f"How much do you currently spend on {topic} per month?",
         "type": "multiple_choice", "choices": ["$0", "$1-100", "$100-500", "$500-2000", "$2000+"]},
        {"title": f"Would you switch to a better {topic} solution if it existed?",
         "type": "multiple_choice", "choices": ["Definitely yes", "Probably yes", "Maybe", "Probably not", "Definitely not"]},
        {"title": f"What features matter most to you in a {topic} solution?", "type": "long_text"},
    ][:questions_count]
    return await _create_survey(
        title=f"Market Research: {topic} for {audience}",
        questions=json.dumps(survey_questions))



async def _get_economic_indicators(indicators: str, country: str = "us") -> str:
    """Get macroeconomic indicators."""
    indicator_list = [i.strip().lower() for i in indicators.split(",")]

    # FRED series IDs mapped from common indicator names
    FRED_SERIES_MAP = {
        "gdp": "GDP",
        "unrate": "UNRATE",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "inflation": "CPIAUCSL",
        "cpiaucsl": "CPIAUCSL",
        "fedfunds": "FEDFUNDS",
        "fed_rate": "FEDFUNDS",
        "t10y2y": "T10Y2Y",
        "yield_curve": "T10Y2Y",
        "payems": "PAYEMS",
        "nonfarm_payroll": "PAYEMS",
    }

    if settings.fred_api_key:
        results = {}
        for ind in indicator_list:
            series_id = FRED_SERIES_MAP.get(ind, ind.upper())
            try:
                resp = await _http.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": settings.fred_api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 12,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    observations = data.get("observations", [])
                    latest = observations[0] if observations else {}
                    results[ind] = {
                        "series_id": series_id,
                        "latest_value": latest.get("value"),
                        "latest_date": latest.get("date"),
                        "recent_observations": [
                            {"date": o.get("date"), "value": o.get("value")}
                            for o in observations[:6]
                        ],
                        "source": "FRED (Federal Reserve Economic Data)",
                    }
                else:
                    results[ind] = {"series_id": series_id, "error": f"FRED returned {resp.status_code}", "note": "Use web_search as fallback"}
            except Exception as exc:
                results[ind] = {"series_id": series_id, "error": str(exc)}

        return json.dumps({
            "country": country,
            "indicators": results,
            "data_sources": ["FRED (Federal Reserve Economic Data): fred.stlouisfed.org"],
            "note": "Live data from FRED API.",
        })

    # --- Stub fallback when no FRED key configured ---
    indicator_data = {
        "gdp": {"name": "GDP Growth Rate", "source": "BEA (Bureau of Economic Analysis)", "frequency": "Quarterly", "lag": "1 month after quarter end", "impact": "Overall economic health — affects consumer spending and business investment"},
        "cpi": {"name": "Consumer Price Index (Inflation)", "source": "BLS (Bureau of Labor Statistics)", "frequency": "Monthly", "lag": "2 weeks", "impact": "Pricing power, cost structure, wage pressure — directly affects margins"},
        "unemployment": {"name": "Unemployment Rate", "source": "BLS", "frequency": "Monthly", "lag": "1 week", "impact": "Labor market tightness — affects hiring costs, talent availability"},
        "fed_rate": {"name": "Federal Funds Rate", "source": "Federal Reserve", "frequency": "8x per year (FOMC)", "lag": "Same day", "impact": "Cost of capital, loan rates, credit availability — affects expansion decisions"},
        "consumer_confidence": {"name": "Consumer Confidence Index", "source": "Conference Board", "frequency": "Monthly", "lag": "Same week", "impact": "B2C spending intent — leading indicator of revenue trends"},
        "pmi": {"name": "Purchasing Managers Index", "source": "ISM", "frequency": "Monthly", "lag": "1 day", "impact": "Manufacturing/services expansion — leading economic indicator. >50 = expansion"},
        "housing": {"name": "Housing Starts & Permits", "source": "Census Bureau", "frequency": "Monthly", "lag": "2 weeks", "impact": "Construction activity, consumer wealth effect, regional economic health"},
    }

    results = {}
    for ind in indicator_list:
        if ind in indicator_data:
            results[ind] = indicator_data[ind]
        else:
            results[ind] = {"name": ind, "note": "Use web_search to find current value and trend"}

    return json.dumps({
        "country": country,
        "indicators": results,
        "data_sources": [
            "FRED (Federal Reserve Economic Data): fred.stlouisfed.org",
            "BLS: bls.gov/data",
            "BEA: bea.gov",
            "Trading Economics: tradingeconomics.com",
        ],
        "note": "Stub data — configure FRED_API_KEY for live values.",
    })



async def _get_industry_report(industry: str, report_type: str = "all") -> str:
    """Get industry-specific intelligence."""
    try:
        # Use web search to gather real-time industry data
        search_query = f"{industry} industry report trends {report_type} 2024 2025"
        resp = await _http.get(f"https://hn.algolia.com/api/v1/search?query={industry}&tags=story&hitsPerPage=5")
        hn_mentions = []
        if resp.status_code == 200:
            for h in resp.json().get("hits", [])[:5]:
                hn_mentions.append({"title": h.get("title", ""), "points": h.get("points", 0), "url": h.get("url", "")})

        return json.dumps({
            "industry": industry,
            "report_type": report_type,
            "framework": {
                "market_size": f"Use web_search: '{industry} market size TAM SAM SOM 2025'",
                "growth_rate": f"Use web_search: '{industry} industry growth rate CAGR forecast'",
                "funding_activity": f"Use web_search: '{industry} funding rounds VC investment 2024 2025'",
                "ma_activity": f"Use web_search: '{industry} mergers acquisitions deals 2024 2025'",
                "key_players": f"Use web_search: '{industry} top companies market leaders'",
                "disruptions": f"Use web_search: '{industry} disruption AI technology trends'",
            },
            "hn_buzz": hn_mentions,
            "recommended_sources": [
                f"CB Insights: {industry} research",
                f"McKinsey/BCG: {industry} sector reports",
                f"Gartner/Forrester: {industry} Magic Quadrant",
                f"Pitchbook: {industry} VC/PE data",
                "Crunchbase: Funding and company data",
            ],
        })
    except Exception as e:
        return json.dumps({"industry": industry, "error": str(e)})



async def _get_regulatory_updates(categories: str, jurisdiction: str = "federal") -> str:
    """Get regulatory and policy updates."""
    cat_list = [c.strip().lower() for c in categories.split(",")]

    if settings.newsapi_key:
        # Build a targeted query from categories + jurisdiction
        cats_str = " OR ".join(cat_list) if "all" not in cat_list else "regulation policy law compliance"
        query = f"({cats_str}) {jurisdiction} regulation"
        try:
            resp = await _http.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "apiKey": settings.newsapi_key,
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                    "language": "en",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                regulatory_news = [
                    {
                        "title": a.get("title"),
                        "source": a.get("source", {}).get("name"),
                        "published_at": a.get("publishedAt"),
                        "url": a.get("url"),
                        "description": a.get("description"),
                    }
                    for a in articles
                ]
                return json.dumps({
                    "jurisdiction": jurisdiction,
                    "categories": cat_list,
                    "regulatory_intelligence": regulatory_news,
                    "action_items": [
                        "Review articles for specific regulation details and compliance deadlines",
                        "Cross-reference with state-specific requirements for your geography",
                        "Set calendar reminders for key compliance deadlines",
                    ],
                    "note": "Live regulatory news from NewsAPI.",
                })
            else:
                logger.warning("NewsAPI returned %s for regulatory updates, falling back to stub", resp.status_code)
        except Exception as exc:
            logger.warning("NewsAPI error for regulatory updates: %s", exc)

    # --- Fallback: static framework when no key or API error ---
    regulatory_framework = {
        "tax": {"key_bodies": ["IRS", "State DOR"], "recent_focus": ["TCJA sunset provisions", "Digital services taxes", "Crypto reporting (Form 1099-DA)", "Corporate AMT changes"], "monitor": "IRS.gov/newsroom, Tax Foundation"},
        "labor": {"key_bodies": ["DOL", "NLRB", "State agencies"], "recent_focus": ["Independent contractor rule (ABC test)", "Minimum wage changes", "Overtime threshold", "Non-compete ban proposals", "Paid leave mandates"], "monitor": "DOL.gov, SHRM.org"},
        "privacy": {"key_bodies": ["FTC", "State AGs"], "recent_focus": ["State privacy laws (comprehensive in 15+ states)", "CCPA/CPRA enforcement", "Children's privacy (COPPA 2.0)", "AI transparency requirements", "Health data protections"], "monitor": "IAPP.org, FTC.gov"},
        "trade": {"key_bodies": ["USTR", "Commerce Dept", "ITC"], "recent_focus": ["China tariffs", "CHIPS Act implementation", "Export controls on AI/semiconductors", "Digital trade agreements"], "monitor": "USTR.gov, Commerce.gov"},
        "financial": {"key_bodies": ["SEC", "CFPB", "FinCEN"], "recent_focus": ["Beneficial ownership reporting (BOI)", "Crypto regulation", "AI in financial services", "Consumer protection enforcement"], "monitor": "SEC.gov, CFPB.gov"},
    }

    results = {}
    for cat in cat_list:
        if cat == "all":
            results = regulatory_framework
            break
        elif cat in regulatory_framework:
            results[cat] = regulatory_framework[cat]

    return json.dumps({
        "jurisdiction": jurisdiction,
        "categories": cat_list,
        "regulatory_intelligence": results,
        "action_items": [
            "Use web_search for specific regulation details and compliance deadlines",
            "Cross-reference with state-specific requirements for your geography",
            "Set calendar reminders for key compliance deadlines",
        ],
        "note": "Stub data — configure NEWSAPI_KEY for live regulatory news.",
    })



async def _build_knowledge_graph(domains: str = "", entity_types: str = "") -> str:
    """Design the entity relationship graph for institutional knowledge."""
    return json.dumps({
        "graph_schema": {
            "node_types": {
                "company": ["name", "industry", "size", "icp_match_score", "relationship_status"],
                "person": ["name", "title", "company", "contact_info", "interaction_history"],
                "industry": ["name", "market_size", "growth_rate", "key_players", "trends"],
                "strategy": ["type", "channel", "effectiveness_score", "last_used", "context"],
                "tool": ["name", "category", "api_cost", "internal_alternative", "usage_count"],
                "outcome": ["metric", "value", "campaign_id", "agent_id", "timestamp"],
                "content": ["type", "platform", "performance", "audience_reaction", "reusable_patterns"],
            },
            "edge_types": [
                "works_at", "contacted_by", "converted_to_client", "churned",
                "competes_with", "partners_with", "targets_icp",
                "produced_by_agent", "used_in_campaign", "resulted_in",
                "similar_to", "contradicts", "supersedes",
            ],
            "indexes": ["by_freshness", "by_confidence", "by_domain", "by_agent"],
        },
        "storage": "Supabase (structured) + vector embeddings (semantic search)",
        "capacity": "Start with 10K nodes, scale to 1M+",
    })



async def _create_knowledge_entry(category: str, content: str, source: str = "", confidence: str = "verified", tags: str = "") -> str:
    """Add a fact or insight to the knowledge base."""
    import uuid as _uuid
    return json.dumps({
        "id": f"KB-{str(_uuid.uuid4())[:8].upper()}",
        "category": category,
        "content": content[:500],
        "source": source,
        "confidence": confidence,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
        "created": "now",
        "freshness_expiry": {"market_data": "24h", "competitor_intel": "7d", "industry_trend": "30d", "client_pattern": "90d", "strategy_insight": "180d"}.get(category, "30d"),
        "status": "active",
    })



async def _query_knowledge_base(query: str, domain: str = "", min_confidence: str = "inferred") -> str:
    """Semantic search across accumulated knowledge."""
    return json.dumps({
        "query": query,
        "domain": domain or "all",
        "min_confidence": min_confidence,
        "results": [],
        "note": "Knowledge base is building. Results will populate as agents accumulate data from tool calls, client interactions, and market research. Every agent run adds to the knowledge base automatically.",
        "coverage_status": "Phase 1: Accumulation — all tool outputs being captured and categorized",
    })



async def _track_api_dependency(api_name: str, call_count: str = "0", avg_cost: str = "0", internal_coverage: str = "0") -> str:
    """Log external API usage for internalization planning."""
    return json.dumps({
        "api": api_name,
        "monthly_calls": int(call_count),
        "avg_cost_per_call": f"${float(avg_cost):.4f}",
        "monthly_cost": f"${int(call_count) * float(avg_cost):.2f}",
        "internal_coverage_pct": f"{internal_coverage}%",
        "internalization_readiness": "Ready" if float(internal_coverage) > 80 else "Building" if float(internal_coverage) > 30 else "Accumulating",
        "recommendation": f"{'Can replace with internal knowledge' if float(internal_coverage) > 80 else 'Continue accumulating data — ' + str(100 - int(float(internal_coverage))) + '% more coverage needed'}",
    })



async def _calculate_knowledge_coverage(domain: str = "all") -> str:
    """Score self-sufficiency by knowledge domain."""
    return json.dumps({
        "domain": domain,
        "coverage_by_domain": {
            "market_data": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Replace web_search for common queries"},
            "competitor_intel": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Internal competitive database"},
            "icp_patterns": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Predict ICP fit without research"},
            "content_patterns": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Generate content from internal playbooks"},
            "pricing_intelligence": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Internal pricing models"},
            "industry_knowledge": {"coverage_pct": 0, "entries": 0, "status": "accumulating", "target": "Self-serve industry reports"},
        },
        "overall_self_sufficiency": "0% — Phase 1: Data accumulation in progress",
        "milestone": "Phase 1: 0-20% (accumulate) → Phase 2: 20-50% (organize) → Phase 3: 50-80% (predict) → Phase 4: 80%+ (self-sufficient)",
    })



async def _detect_knowledge_gaps(domain: str = "", priority: str = "high") -> str:
    """Identify missing knowledge areas ranked by business impact."""
    return json.dumps({
        "domain": domain or "all",
        "priority": priority,
        "gaps": [
            {"domain": "market_data", "gap": "No internal economic indicators dataset", "impact": "high", "research_plan": "Accumulate from get_economic_indicators and get_market_data calls"},
            {"domain": "competitor_intel", "gap": "No competitor pricing history", "impact": "high", "research_plan": "Track competitor pricing on every competitive_intel agent run"},
            {"domain": "client_patterns", "gap": "No client behavior models", "impact": "high", "research_plan": "Log every client interaction, build cohort models after 10+ clients"},
            {"domain": "content_performance", "gap": "No content effectiveness data", "impact": "medium", "research_plan": "Track engagement metrics for every piece of content produced"},
        ],
        "note": "Gaps auto-fill as agents run and accumulate data. Priority gaps drive research agent scheduling.",
    })



async def _build_prediction_model(model_type: str, data_requirements: str = "") -> str:
    """Design predictive model from accumulated data."""
    models = {
        "lead_scoring": {"inputs": ["ICP match", "engagement signals", "company size", "tech stack"], "output": "Conversion probability 0-100", "min_data": "50+ leads with outcome data"},
        "churn_prediction": {"inputs": ["Engagement frequency", "CSAT trend", "support tickets", "usage decline"], "output": "Churn risk: low/medium/high", "min_data": "20+ clients with 6mo+ history"},
        "pricing_optimization": {"inputs": ["Client size", "service scope", "competitive pricing", "win/loss history"], "output": "Optimal price point", "min_data": "30+ proposals with win/loss data"},
        "channel_effectiveness": {"inputs": ["Channel", "content type", "audience segment", "timing"], "output": "Expected ROI by channel", "min_data": "100+ campaign data points"},
    }
    model = models.get(model_type, {"inputs": ["Custom"], "output": "Custom prediction", "min_data": "Sufficient historical data"})
    return json.dumps({
        "model_type": model_type,
        "specification": model,
        "status": "Design phase — accumulating training data",
        "note": "Model becomes available when minimum data threshold is met. All agent outputs contribute to training data.",
    })



async def _build_world_state(domains: str = "all") -> str:
    """Create real-time world state model."""
    return json.dumps({
        "world_state": {
            "economy": {"status": "Query get_economic_indicators for current state", "indicators": ["GDP", "CPI", "Unemployment", "Fed Rate", "Consumer Confidence"], "update_frequency": "daily"},
            "markets": {"status": "Query get_market_data for live data", "tracked": ["S&P 500", "Sector indices", "VIX", "10Y yield", "DXY"], "update_frequency": "real-time"},
            "technology": {"status": "Scan HN, Reddit, tech news", "tracked": ["AI developments", "Platform changes", "New tools/frameworks"], "update_frequency": "daily"},
            "culture": {"status": "Monitor social platforms", "tracked": ["Trending topics", "Social movements", "Cultural moments", "Viral content"], "update_frequency": "hourly"},
            "politics": {"status": "Monitor regulatory feeds", "tracked": ["Policy changes", "Regulatory actions", "Tax law updates", "Trade policy"], "update_frequency": "daily"},
            "weather_events": {"status": "Monitor impact events", "tracked": ["Supply chain disruptions", "Regional events affecting business"], "update_frequency": "as-needed"},
        },
        "agent_integration": "Every agent receives relevant world state context before executing",
    })



async def _map_social_climate(topic: str, platforms: str = "all") -> str:
    """Analyze current social sentiment on a topic."""
    platform_list = [p.strip() for p in platforms.split(",")] if platforms != "all" else ["linkedin", "twitter", "reddit", "tiktok", "hackernews"]

    if settings.newsapi_key:
        try:
            resp = await _http.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": topic,
                    "apiKey": settings.newsapi_key,
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "language": "en",
                },
            )
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                # Simple sentiment breakdown from titles
                positive_words = {"surge", "rise", "gain", "growth", "success", "win", "boom", "rally", "profit", "record", "milestone", "breakthrough", "improve", "strong", "positive", "bullish", "thrive", "lead", "launch", "expand"}
                negative_words = {"fall", "drop", "crash", "loss", "fail", "decline", "plunge", "risk", "crisis", "warn", "cut", "layoff", "ban", "lawsuit", "fine", "scandal", "concern", "weak", "miss", "slump"}
                sentiment = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
                for a in articles:
                    title_lower = (a.get("title") or "").lower()
                    has_pos = any(w in title_lower for w in positive_words)
                    has_neg = any(w in title_lower for w in negative_words)
                    if has_pos and has_neg:
                        sentiment["mixed"] += 1
                    elif has_pos:
                        sentiment["positive"] += 1
                    elif has_neg:
                        sentiment["negative"] += 1
                    else:
                        sentiment["neutral"] += 1
                total = max(len(articles), 1)
                sentiment_pct = {k: round(v / total * 100, 1) for k, v in sentiment.items()}
                news_items = [
                    {
                        "title": a.get("title"),
                        "source": a.get("source", {}).get("name"),
                        "published_at": a.get("publishedAt"),
                        "url": a.get("url"),
                    }
                    for a in articles[:10]
                ]
                return json.dumps({
                    "topic": topic,
                    "platforms": platform_list,
                    "analysis_framework": {
                        "sentiment": sentiment_pct,
                        "volume": f"{len(articles)} articles found via NewsAPI",
                        "key_narratives": "Derived from top news articles below",
                        "influencer_positions": "See article sources for authoritative voices",
                        "generational_split": "Infer from platform context",
                    },
                    "news_articles": news_items,
                    "data_sources": ["NewsAPI — live news coverage"],
                    "actionable_output": f"For {topic}: sentiment is {max(sentiment_pct, key=sentiment_pct.get)} overall. Review articles for messaging cues.",
                    "note": "Live sentiment derived from NewsAPI article titles.",
                })
            else:
                logger.warning("NewsAPI returned %s for social climate, falling back to stub", resp.status_code)
        except Exception as exc:
            logger.warning("NewsAPI error for social climate: %s", exc)

    # --- Stub fallback ---
    return json.dumps({
        "topic": topic,
        "platforms": platform_list,
        "analysis_framework": {
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
            "volume": "Track mention volume over time to detect trend shifts",
            "key_narratives": "Identify the 3-5 dominant narratives around this topic",
            "influencer_positions": "Map key voices and their stances",
            "generational_split": "How Gen Z vs Millennial vs Gen X view this topic",
        },
        "data_sources": [f"Use search_reddit for r/{topic.replace(' ', '')} sentiment", "Use search_hackernews for tech community view", "Use web_search for broader media sentiment"],
        "actionable_output": f"For {topic}: recommended tone, messaging do's and don'ts, platforms to lean into vs avoid",
        "note": "Stub data — configure NEWSAPI_KEY for live sentiment analysis.",
    })



async def _build_cultural_calendar(geography: str = "us", industry: str = "", months: str = "3") -> str:
    """Map cultural moments and seasonal patterns."""
    return json.dumps({
        "geography": geography,
        "industry": industry,
        "months_ahead": int(months),
        "calendar_categories": {
            "holidays": "Federal holidays, cultural celebrations, religious observances",
            "industry_events": f"Conferences, trade shows, award deadlines for {industry or 'your industry'}",
            "buying_seasons": "Budget cycles, fiscal year ends, seasonal demand patterns",
            "cultural_moments": "Awareness months, social movements, viral events",
            "content_hooks": "Annual events that create content opportunities (Earth Day, Small Business Saturday, etc.)",
        },
        "for_each_event": {
            "what": "Event/moment name and date",
            "relevance": "How it affects this business (1-5 scale)",
            "content_opportunity": "Specific content angle",
            "messaging_adjustment": "Tone/messaging changes needed",
            "risk": "Any sensitivity or controversy to avoid",
        },
    })



async def _track_platform_culture(platform: str) -> str:
    """Map norms and best practices for a specific platform."""
    cultures = {
        "linkedin": {"tone": "Professional but human", "format": "Multi-paragraph stories, carousels, polls", "taboo": "Hard selling, engagement bait, irrelevant personal stories", "algorithm": "Favors comments > likes, dwell time, native content"},
        "twitter": {"tone": "Punchy, opinionated, real-time", "format": "Hot takes, threads, quote tweets, memes", "taboo": "Long-form without value, promotional links in first tweet", "algorithm": "Favors replies, bookmarks, early engagement velocity"},
        "reddit": {"tone": "Authentic, humble, value-first", "format": "Helpful comments, detailed answers, AMAs", "taboo": "Self-promotion, marketing-speak, anything that smells like an ad", "algorithm": "Community-moderated, karma-based credibility"},
        "tiktok": {"tone": "Authentic, entertaining, educational", "format": "15-60s vertical video, trending sounds, native style", "taboo": "Corporate tone, over-produced content, ignoring trends", "algorithm": "Completion rate > followers, fresh accounts can go viral"},
        "hackernews": {"tone": "Technical, data-driven, skeptical", "format": "Show HN, technical deep-dives, thoughtful comments", "taboo": "Marketing, clickbait, unsubstantiated claims, fluff", "algorithm": "Points + comments, recency, no gaming tolerance"},
        "youtube": {"tone": "Authoritative yet approachable", "format": "Shorts (30-60s) and long-form (8-15min)", "taboo": "Clickbait without delivering, stolen content", "algorithm": "Watch time, CTR on thumbnails, session time"},
    }
    return json.dumps({
        "platform": platform,
        "culture": cultures.get(platform.lower(), {"note": f"Research {platform} norms with web_search"}),
        "best_posting_times": "Use web_search for current best-times data for your specific audience",
        "content_pillars": "Adapt your 3-5 content pillars to this platform's native format",
    })



async def _map_geographic_context(geography: str, business_type: str = "") -> str:
    """Build spatial awareness for business operations."""
    return json.dumps({
        "geography": geography,
        "context": {
            "regulatory": f"Use get_regulatory_updates for {geography}-specific regulations",
            "cultural": f"Use web_search for business culture norms in {geography}",
            "competitive": f"Use web_search for competitors in {geography}",
            "economic": f"Use get_economic_indicators for {geography} economic data",
            "talent": f"Use web_search for hiring market in {geography}",
        },
        "considerations": [
            "Timezone implications for client communication",
            "Regional language/dialect preferences in content",
            "Local regulations (privacy, employment, tax)",
            "Cultural sensitivity in marketing messaging",
            "Regional platform preferences (some regions favor different social platforms)",
        ],
    })



async def _build_temporal_model(industry: str = "", business_stage: str = "") -> str:
    """Build business cycle and timing awareness."""
    return json.dumps({
        "industry": industry,
        "business_stage": business_stage,
        "temporal_layers": {
            "daily": {"patterns": "Peak engagement hours, optimal send times, meeting windows", "data_source": "Analytics + platform insights"},
            "weekly": {"patterns": "Best days for content, outreach, reporting", "data_source": "Historical performance data"},
            "monthly": {"patterns": "Content calendar, billing cycles, reporting cadence", "data_source": "Business operations data"},
            "quarterly": {"patterns": "Budget cycles, QBRs, seasonal demand, tax deadlines", "data_source": "Financial calendar + industry norms"},
            "annual": {"patterns": "Major holidays, industry conferences, fiscal planning, renewal seasons", "data_source": "Industry calendar + historical data"},
            "multi_year": {"patterns": "Technology adoption curves, market maturity, business lifecycle stage", "data_source": "Industry reports + trend analysis"},
        },
        "current_position": {
            "business_cycle": "Determine via get_economic_indicators (expansion/peak/contraction/trough)",
            "technology_cycle": "Determine via web_search for current adoption curves",
            "industry_cycle": f"Determine via get_industry_report for {industry or 'your industry'}",
        },
    })



async def _run_scenario_analysis(scenario: str, business_name: str = "", impact_areas: str = "") -> str:
    """Run what-if business modeling."""
    areas = [a.strip() for a in impact_areas.split(",")] if impact_areas else ["revenue", "clients", "operations", "hiring", "marketing"]
    return json.dumps({
        "scenario": scenario,
        "business": business_name,
        "analysis": {area: {"impact": "Assess with current data", "probability": "Estimate", "mitigation": "Develop contingency"} for area in areas},
        "framework": {
            "step_1": "Define scenario parameters (severity, duration, trigger)",
            "step_2": f"Assess impact on each area: {', '.join(areas)}",
            "step_3": "Estimate probability (low/medium/high) and timeline",
            "step_4": "Develop mitigation strategies for each impact area",
            "step_5": "Define trigger signals that indicate scenario is materializing",
            "step_6": "Create response playbook: immediate actions, 30-day plan, 90-day plan",
        },
        "common_scenarios": [
            "Economic recession: demand drops 20-40%",
            "Major competitor launch: pricing pressure",
            "Regulation change: compliance costs increase",
            "Key client churn: revenue concentration risk",
            "AI disruption: commoditization of core service",
            "Viral moment: sudden demand spike (positive or negative)",
        ],
    })



async def _build_sentiment_tracker(topics: str, platforms: str = "all") -> str:
    """Configure real-time sentiment monitoring."""
    topic_list = [t.strip() for t in topics.split(",")]
    return json.dumps({
        "tracked_topics": topic_list,
        "platforms": platforms,
        "monitoring_config": {
            "data_sources": ["Reddit API", "HN Algolia API", "Google Trends", "Twitter/X API", "News RSS feeds"],
            "sentiment_model": "Classify each mention: positive/negative/neutral with confidence score",
            "aggregation": "Rolling 24hr, 7d, 30d sentiment scores per topic",
            "alerts": {
                "sentiment_shift": "Topic sentiment changes >20% in 24 hours",
                "volume_spike": "Mention volume >3x normal in 4 hours",
                "negative_surge": "Negative sentiment >60% for any tracked topic",
            },
        },
        "output": "Daily sentiment digest injected into agent context for relevant agents",
    })



def register_research_tools(registry):
    """Register all research tools with the given registry."""
    from models import ToolParameter

    registry.register("web_search", "Search the web for information about companies, industries, trends, or any topic.",
        [ToolParameter(name="query", description="Search query"),
         ToolParameter(name="num_results", type="integer", description="Results count (1-10)", required=False)],
        _web_search, "web")

    registry.register("web_scrape", "Fetch and extract text from a URL. Use to read company sites, blog posts, landing pages.",
        [ToolParameter(name="url", description="Full URL to scrape"),
         ToolParameter(name="max_chars", type="integer", description="Max chars to return", required=False)],
        _web_scrape, "web")

    registry.register("analyze_website", "Analyze a website for content quality, word count, and basic SEO signals.",
        [ToolParameter(name="url", description="URL to analyze")],
        _analyze_website, "web")

    # ── Prospecting Tools ──

    registry.register("company_research", "Research a company — returns industry, size, revenue, description, LinkedIn. Uses Apollo if configured.",
        [ToolParameter(name="company_name", description="Company name"),
         ToolParameter(name="domain", description="Company domain if known", required=False)],
        _company_research, "prospecting")

    registry.register("get_market_data", "Get market research data — market size, traffic, trends.",
        [ToolParameter(name="query", description="Market/industry query or domain"),
         ToolParameter(name="data_type", description="Type: market_size, website_traffic, trends", required=False)],
        _get_market_data, "research")

    registry.register("track_competitor", "Track competitor — site content, tech stack, social presence.",
        [ToolParameter(name="competitor_domain", description="Competitor's domain"),
         ToolParameter(name="metrics", description="What to track: all, site, tech, social", required=False)],
        _track_competitor, "research")

    registry.register("run_market_survey", "Generate and create a market research survey.",
        [ToolParameter(name="topic", description="Survey topic"),
         ToolParameter(name="audience", description="Target audience description"),
         ToolParameter(name="questions_count", type="integer", description="Number of questions (1-10)", required=False)],
        _run_market_survey, "research")

    # ── Procurement Tools ──

    registry.register("get_market_data", "Get live market data — indices, commodities, currencies, sector performance.",
        [ToolParameter(name="symbols", description="Comma-separated symbols: SPY, QQQ, GLD, DXY, BTC, or sector names"),
         ToolParameter(name="timeframe", description="Timeframe: 1d, 1w, 1m, 3m, 1y", required=False)],
        _get_market_data, "research")

    registry.register("get_economic_indicators", "Get macro economic indicators — GDP, CPI, unemployment, interest rates, consumer confidence.",
        [ToolParameter(name="indicators", description="Comma-separated: gdp, cpi, unemployment, fed_rate, consumer_confidence, pmi, housing"),
         ToolParameter(name="country", description="Country: us, eu, uk, global", required=False)],
        _get_economic_indicators, "research")

    registry.register("get_industry_report", "Get industry-specific intelligence — trends, M&A, funding, market sizing.",
        [ToolParameter(name="industry", description="Industry: saas, marketing, consulting, ecommerce, fintech, healthcare, etc."),
         ToolParameter(name="report_type", description="Type: trends, funding, market_size, competitive, all", required=False)],
        _get_industry_report, "research")

    registry.register("get_regulatory_updates", "Get regulatory and policy updates affecting businesses — tax, labor, privacy, trade.",
        [ToolParameter(name="categories", description="Comma-separated: tax, labor, privacy, trade, financial, all"),
         ToolParameter(name="jurisdiction", description="Jurisdiction: federal, state name, or eu", required=False)],
        _get_regulatory_updates, "research")

    # ── Support & Helpdesk Tools ──

    registry.register("build_knowledge_graph", "Design entity relationship graph for institutional knowledge.",
        [ToolParameter(name="domains", description="Knowledge domains: market, competitor, client, content, strategy", required=False),
         ToolParameter(name="entity_types", description="Entity types to track", required=False)],
        _build_knowledge_graph, "research")

    registry.register("create_knowledge_entry", "Add a fact or insight to the institutional knowledge base.",
        [ToolParameter(name="category", description="Category: market_data, competitor_intel, icp_patterns, content_patterns, pricing, industry"),
         ToolParameter(name="content", description="The knowledge content"),
         ToolParameter(name="source", description="Source: tool_output, client_call, agent_learning, web_research", required=False),
         ToolParameter(name="confidence", description="Confidence: verified, inferred, hypothesized", required=False),
         ToolParameter(name="tags", description="Comma-separated tags", required=False)],
        _create_knowledge_entry, "research")

    registry.register("query_knowledge_base", "Semantic search across accumulated institutional knowledge.",
        [ToolParameter(name="query", description="Natural language query"),
         ToolParameter(name="domain", description="Filter by domain", required=False),
         ToolParameter(name="min_confidence", description="Minimum confidence: verified, inferred, hypothesized", required=False)],
        _query_knowledge_base, "research")

    registry.register("track_api_dependency", "Log external API usage for internalization planning.",
        [ToolParameter(name="api_name", description="API name"),
         ToolParameter(name="call_count", description="Monthly call count", required=False),
         ToolParameter(name="avg_cost", description="Average cost per call", required=False),
         ToolParameter(name="internal_coverage", description="% of queries answerable internally", required=False)],
        _track_api_dependency, "research")

    registry.register("calculate_knowledge_coverage", "Score self-sufficiency by knowledge domain.",
        [ToolParameter(name="domain", description="Domain to assess or 'all'", required=False)],
        _calculate_knowledge_coverage, "research")

    registry.register("detect_knowledge_gaps", "Identify missing knowledge areas ranked by business impact.",
        [ToolParameter(name="domain", description="Domain to analyze", required=False),
         ToolParameter(name="priority", description="Priority filter: high, medium, low", required=False)],
        _detect_knowledge_gaps, "research")

    registry.register("build_prediction_model", "Design predictive model from accumulated data (lead scoring, churn, pricing).",
        [ToolParameter(name="model_type", description="Model: lead_scoring, churn_prediction, pricing_optimization, channel_effectiveness"),
         ToolParameter(name="data_requirements", description="Additional data requirements", required=False)],
        _build_prediction_model, "research")

    # ── Agent Workspace & Workflow Tools ──

    registry.register("build_world_state", "Create real-time world state model across economy, markets, tech, culture.",
        [ToolParameter(name="domains", description="Domains: economy, markets, technology, culture, politics, all", required=False)],
        _build_world_state, "research")

    registry.register("map_social_climate", "Analyze current social sentiment on a topic across platforms.",
        [ToolParameter(name="topic", description="Topic to analyze"),
         ToolParameter(name="platforms", description="Platforms: linkedin, twitter, reddit, tiktok, hackernews, all", required=False)],
        _map_social_climate, "research")

    registry.register("build_cultural_calendar", "Map cultural moments and seasonal patterns for next N months.",
        [ToolParameter(name="geography", description="Geography: us, uk, global, or specific region", required=False),
         ToolParameter(name="industry", description="Industry for relevant events", required=False),
         ToolParameter(name="months", description="Months ahead to plan", required=False)],
        _build_cultural_calendar, "research")

    registry.register("track_platform_culture", "Map norms, best practices, and algorithm preferences for a platform.",
        [ToolParameter(name="platform", description="Platform: linkedin, twitter, reddit, tiktok, hackernews, youtube")],
        _track_platform_culture, "research")

    registry.register("map_geographic_context", "Build spatial awareness for business operations in a geography.",
        [ToolParameter(name="geography", description="Geography to analyze"),
         ToolParameter(name="business_type", description="Type of business for context", required=False)],
        _map_geographic_context, "research")

    registry.register("build_temporal_model", "Build business cycle and timing awareness for the industry.",
        [ToolParameter(name="industry", description="Industry for cycle analysis", required=False),
         ToolParameter(name="business_stage", description="Current stage: startup, growth, scale, mature", required=False)],
        _build_temporal_model, "research")

    registry.register("run_scenario_analysis", "Run what-if business modeling for strategic planning.",
        [ToolParameter(name="scenario", description="Scenario to model (e.g. 'recession', 'competitor launch', 'regulation change')"),
         ToolParameter(name="business_name", description="Business name", required=False),
         ToolParameter(name="impact_areas", description="Areas to assess: revenue, clients, operations, hiring, marketing", required=False)],
        _run_scenario_analysis, "research")

    registry.register("build_sentiment_tracker", "Configure real-time sentiment monitoring for topics across platforms.",
        [ToolParameter(name="topics", description="Comma-separated topics to track"),
         ToolParameter(name="platforms", description="Platforms to monitor: all, or comma-separated list", required=False)],
        _build_sentiment_tracker, "research")

    # ── Figma Design Tools ──

