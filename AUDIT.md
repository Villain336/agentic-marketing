# SUPERVISOR — Full Repository Audit

**Date:** 2026-03-20
**Branch:** `claude/full-repo-audit-Jf1Q8`
**Scope:** Complete codebase review — architecture, security, code quality, gaps, and recommendations

---

## 1. REPOSITORY OVERVIEW

**Project:** Supervisor — Autonomous Agentic Marketing Agency SaaS
**Vision:** "Shopify for agentic businesses" — user provides a business idea, 12 AI agents do everything else (prospecting, outreach, content, ads, client success, site launch, legal, GTM, email, PPC).

### File Inventory (15 files)

```
BLUEPRINT.md                              1,064 lines — Master spec / 11-phase roadmap
AUDIT.md                                  this file
supervisor-complete/
├── README.md                             49 lines  — Project overview + quick start
├── backend/
│   ├── config.py                         111 lines — Env-based settings, 3-provider chain
│   ├── models.py                         255 lines — Pydantic models (tools, agents, campaigns, API)
│   ├── providers.py                      481 lines — Anthropic/OpenAI/Google adapters + failover
│   ├── tools.py                          213 lines — Tool registry + 8 built-in tools
│   ├── engine.py                         173 lines — ReAct reasoning loop
│   ├── agents.py                         156 lines — 12 agent configurations
│   ├── main.py                           217 lines — FastAPI app with SSE streaming
│   ├── requirements.txt                  5 lines   — Python dependencies
│   └── Dockerfile                        7 lines   — Production container
├── frontend/
│   ├── index.html                        1,325 lines — Full SPA (React CDN)
│   └── personas.html                     1,365 lines — Persona simulation engine
```

**Total:** ~4,421 lines of code (excluding BLUEPRINT)

---

## 2. ARCHITECTURE ASSESSMENT

### 2.1 Backend (Python/FastAPI)

**Rating: SOLID for MVP**

The backend follows a clean layered architecture:

```
main.py (API layer)
  └── engine.py (ReAct reasoning loop)
       ├── providers.py (LLM routing + failover)
       ├── tools.py (tool registry + execution)
       └── agents.py (agent configs + prompts)
  └── models.py (shared data models)
  └── config.py (environment settings)
```

**Provider Failover Chain:**
1. Anthropic Claude (primary) — `claude-sonnet-4-20250514` / `claude-haiku-4-5-20251001`
2. OpenAI GPT (fallback) — `gpt-4o` / `gpt-4o-mini`
3. Google Gemini (last resort) — `gemini-2.0-flash` / `gemini-2.0-flash-lite`

Each provider has:
- Exponential backoff on errors (5s → 15s → 45s → 120s cap)
- Automatic cooldown periods
- Error counting and status tracking
- Normalized tool-calling across all three APIs

**ReAct Engine Loop:**
```
Plan → Act (call tool) → Observe (read result) → Decide (loop or finish)
```
- Streams every step as SSE events
- Enforces max iterations (configurable, default 25)
- Enforces max runtime (configurable, default 300s)
- Memory extraction from final output

**API Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Provider status + active campaigns |
| GET | `/agents` | List all 12 agents with tool info |
| GET | `/providers` | Provider status details |
| POST | `/agent/{id}/run` | Run single agent (SSE stream) |
| POST | `/campaign/run` | Run full 12-agent campaign (SSE stream) |
| GET | `/campaign/{id}` | Get campaign state |
| GET | `/campaign/{id}/memory` | Get campaign memory |
| DELETE | `/campaign/{id}` | Delete campaign |
| POST | `/validate` | Validate output against buyer personas |

### 2.2 Frontend

**Rating: FUNCTIONAL MVP, NEEDS PRODUCTION HARDENING**

**`index.html` — Main Application (React CDN + Babel):**
- React 18 via CDN with in-browser Babel transpilation
- Supabase Auth (email/password) via REST API
- Stripe Checkout with 3 pricing tiers ($2,500 / $7,000 / $15,000/mo)
- 5-step onboarding form
- 12-agent dashboard with SSE streaming output viewer
- Agent grading system, campaign memory display
- Brand training document upload
- Backend status indicator with auto-detection

**`personas.html` — Persona Simulation Engine (Vanilla JS):**
- 8 psychologically-deep buyer personas with cognitive biases
- 8 market contexts (B2B SaaS, Enterprise, Consumer, Healthcare, etc.)
- 8 test types (first impression, pricing, cold email, subject line, etc.)
- Batch testing + individual chat mode
- AI-generated synthesis/insights
- Subject line open rate estimator
- Test history tracking
- Custom `h()` render function (no framework)

### 2.3 Agent System

| # | ID | Label | Role | Tier | Tools | Max Iter |
|---|----|-------|------|------|-------|----------|
| 1 | prospector | Prospector | Lead Intelligence | Standard | prospecting, web | 20 |
| 2 | outreach | Outreach | Sales Automation | Standard | web | 10 |
| 3 | content | Content | SEO & Authority | Standard | web | 10 |
| 4 | social | Social | Audience Growth | Fast | web | 5 |
| 5 | ads | Ads | Paid Acquisition | Standard | web | 8 |
| 6 | cs | Client Success | Retention & Ops | Standard | none | 5 |
| 7 | sitelaunch | Site Launch | Domain/Build/Deploy | Standard | web | 12 |
| 8 | legal | Legal | Compliance & Contracts | Standard | web | 8 |
| 9 | marketing_expert | Marketing Expert | Strategy & Positioning | Standard | web | 12 |
| 10 | procurement | Procurement | Tool & Spend Tracking | Fast | web | 8 |
| 11 | newsletter | Newsletter | Email Campaigns | Standard | web | 8 |
| 12 | ppc | PPC Manager | Ongoing Ad Optimization | Standard | web | 8 |

**Campaign Loop Order:** Prospector → Outreach → Content → Social → Ads → CS → Site Launch
**Operations Layer:** Legal, Marketing Expert, Procurement, Newsletter, PPC

### 2.4 Tool System

| Tool | Category | External API | Status |
|------|----------|-------------|--------|
| web_search | web | Serper.dev | Functional (needs API key) |
| web_scrape | web | Direct HTTP | Functional |
| company_research | prospecting | Apollo.io | Functional (needs API key), falls back to web_search |
| find_contacts | prospecting | Apollo.io / Hunter.io | Functional (needs API key) |
| verify_email | email | Hunter.io | Functional (needs API key) |
| analyze_website | web | Direct HTTP | Functional |
| store_data | memory | None | **STUB — returns mock response** |
| read_data | memory | None | **STUB — returns mock response** |

---

## 3. SECURITY AUDIT

### 3.1 CRITICAL Issues

| # | Severity | Location | Issue | Recommendation |
|---|----------|----------|-------|----------------|
| S1 | **HIGH** | `frontend/index.html:18` | Supabase anon key hardcoded in frontend | This is architecturally expected for Supabase (anon key is public by design), but **Row Level Security (RLS) must be verified** on all Supabase tables. If RLS is not enabled, the anon key grants full read/write access to all data. |
| S2 | **HIGH** | `backend/main.py` (all endpoints) | **No authentication on backend API** — anyone can run agents, create campaigns, delete campaigns | Add JWT verification middleware. Validate Supabase access tokens on every request. |
| S3 | **HIGH** | `frontend/personas.html:428-456` | Anthropic API called directly from browser with no auth headers | This will fail without a CORS proxy. If a user adds their API key, it's exposed client-side. Route through backend instead. |
| S4 | **MEDIUM** | `frontend/index.html:25-45` | Live Stripe payment links hardcoded | Acceptable for MVP but should be environment-driven for staging/production separation. |
| S5 | **MEDIUM** | `backend/tools.py:79` | `web_scrape` has no URL validation | Could be used for SSRF (Server-Side Request Forgery). Add allowlist or block internal IPs (127.0.0.1, 10.x, 169.254.x, etc.). |
| S6 | **MEDIUM** | No `.gitignore` | Risk of committing `.env`, `__pycache__`, credentials | Add `.gitignore` immediately. |
| S7 | **LOW** | `backend/main.py:31` | CORS allows all origins (`allow_origins=["*"]`) | Tighten to specific frontend domains in production. |
| S8 | **LOW** | No rate limiting | Backend endpoints have no rate limiting | Add rate limiting middleware (e.g., slowapi) to prevent abuse. |

### 3.2 Credential Exposure Check

| Item | Status |
|------|--------|
| API keys in source code | **NONE** — all keys loaded from env vars via `config.py` |
| Supabase anon key | Present in `index.html` — expected (public key) |
| Stripe secret key | **NOT in code** — only public payment links |
| `.env` file committed | **NO** — not present in repo |

---

## 4. CODE QUALITY AUDIT

### 4.1 Backend

**Strengths:**
- Consistent code style throughout
- Clean separation of concerns
- Pydantic models provide type safety and validation
- Error handling in provider adapters is thorough
- Memory extraction pattern is elegant (lambda-based extractors per agent)
- Tool registry pattern is extensible

**Issues:**

| # | File | Line(s) | Issue |
|---|------|---------|-------|
| Q1 | `config.py` | 34 | `cors_origins` typed as bare `list` instead of `list[str]` |
| Q2 | `config.py` | 40 | `providers` typed as bare `list` instead of `list[ProviderConfig]` |
| Q3 | `models.py` | 132 | `datetime.utcnow` is deprecated in Python 3.12 — use `datetime.now(timezone.utc)` |
| Q4 | `engine.py` | 82 | `tool_calls: list[ToolCall] = []` mutable default in local scope — not a bug here but could confuse readers |
| Q5 | `providers.py` | 69 | `yield` after `raise NotImplementedError` with `# pragma: no cover` — unusual pattern for abstract async generators |
| Q6 | `tools.py` | 18 | Module-level `httpx.AsyncClient` created at import time — should be created within async context or use lifespan |
| Q7 | `tools.py` | 80-84 | `web_scrape` HTML→text conversion is naive (regex-based) — works for MVP but will break on complex pages |
| Q8 | `main.py` | 34 | In-memory campaign store — data lost on every restart/deploy |
| Q9 | `agents.py` | All | System prompts embedded as f-string lambdas — works but hard to test/iterate independently |
| Q10 | `requirements.txt` | — | No pinned versions (uses `>=`) — builds may break with future releases |

### 4.2 Frontend

**Issues:**

| # | File | Issue |
|---|------|-------|
| F1 | `index.html` | React via CDN + Babel transpilation in browser — ~200ms parsing overhead per page load, not suitable for production |
| F2 | `index.html` | Entire app in a single 1,325-line file — no component separation |
| F3 | `index.html:19` | `API_URL` fallback is `/api` — will 404 unless a reverse proxy is configured |
| F4 | `personas.html` | Calls Anthropic API directly with no API key in headers — requests will be rejected |
| F5 | `personas.html` | No error boundary — API failures show raw error text |
| F6 | Both files | No build step, no minification, no tree-shaking — ships raw source to users |
| F7 | `index.html` | Supabase session not refreshed — tokens will expire after 1 hour |

---

## 5. MISSING FILES & INFRASTRUCTURE

| Item | Status | Impact |
|------|--------|--------|
| `.gitignore` | **MISSING** | Could accidentally commit secrets, cache files, node_modules |
| `.env.example` | **MISSING** (referenced in BLUEPRINT) | Developers won't know what env vars are needed |
| Tests (any) | **MISSING** | Zero test coverage — no unit, integration, or e2e tests |
| CI/CD config | **MISSING** | No GitHub Actions, no automated deployment |
| Database migrations | **MISSING** | BLUEPRINT defines Supabase schema but no migration files |
| Logging config | **BASIC** | Only Python logging to stdout — no structured logging, no log aggregation |
| Health check | **EXISTS** | `/health` endpoint works but doesn't check database connectivity |
| Error monitoring | **MISSING** | No Sentry or equivalent |
| API documentation | **AUTO** | FastAPI auto-generates `/docs` — functional but not customized |

---

## 6. DEPENDENCY AUDIT

### Backend (`requirements.txt`)

| Package | Version Spec | Latest Stable | Notes |
|---------|-------------|---------------|-------|
| fastapi | >=0.115.0 | ~0.115.x | OK — but should pin |
| uvicorn[standard] | >=0.32.0 | ~0.34.x | OK |
| httpx | >=0.28.0 | ~0.28.x | OK |
| pydantic | >=2.10.0 | ~2.11.x | OK |
| python-dotenv | >=1.0.0 | ~1.0.x | OK — but **never imported** in code |

**Note:** `python-dotenv` is listed but never used. The code reads env vars directly via `os.getenv()`. Either add `from dotenv import load_dotenv; load_dotenv()` to `config.py` or remove the dependency.

### Frontend (CDN dependencies)

| Library | Version | Notes |
|---------|---------|-------|
| React | 18 (production) | OK |
| ReactDOM | 18 (production) | OK |
| Babel Standalone | latest | For in-browser JSX transpilation — remove for production |

---

## 7. BLUEPRINT vs REALITY GAP ANALYSIS

The BLUEPRINT defines 11 phases and 22 build items. Current state:

| Phase | Description | Status | Gap |
|-------|-------------|--------|-----|
| 1.1 | Deploy to Railway | **NOT DONE** | Backend not deployed anywhere |
| 1.2 | E2E validation | **NOT DONE** | No deployment to test against |
| 1.3 | Serper API integration | **CODE EXISTS** | Tool code ready, needs API key |
| 1.4 | Apollo API integration | **CODE EXISTS** | Tool code ready, needs API key |
| 2 | 7-stage AI onboarding | **NOT STARTED** | Current onboarding is 5 text fields |
| 3 | Design Agent (13th) | **NOT STARTED** | Only 12 agents exist |
| 4 | Execution tools | **NOT STARTED** | No email sending, social posting, ad deployment, site deploy |
| 5 | Sensing & feedback | **NOT STARTED** | No webhooks, no performance ingestion |
| 6 | Supervisor meta-agent | **NOT STARTED** | No weekly review, no budget reallocation |
| 7 | Agent wallet | **NOT STARTED** | No budget management |
| 8 | Telegram/Slack | **NOT STARTED** | No messaging integration |
| 9 | Multi-campaign | **NOT STARTED** | Single campaign only |
| 10 | Self-organizing agents | **NOT STARTED** | No agent lifecycle management |
| 11 | Persona gauntlet | **PARTIAL** | Frontend exists (`personas.html`), not integrated into backend |

**Bottom line:** The core engine (providers, tools, agents, ReAct loop, SSE streaming) is built and solid. Everything beyond that is roadmap.

---

## 8. RECOMMENDATIONS — PRIORITIZED

### Immediate (Do Before Any Deployment)

1. **Add `.gitignore`**
   ```
   .env
   __pycache__/
   *.pyc
   .venv/
   node_modules/
   .DS_Store
   ```

2. **Add `.env.example`**
   ```
   ANTHROPIC_API_KEY=
   OPENAI_API_KEY=
   GOOGLE_API_KEY=
   SERPER_API_KEY=
   APOLLO_API_KEY=
   HUNTER_API_KEY=
   SENDGRID_API_KEY=
   SUPABASE_URL=
   SUPABASE_ANON_KEY=
   SUPABASE_SERVICE_KEY=
   DEBUG=false
   ```

3. **Add backend auth middleware** — verify Supabase JWT on all `/agent`, `/campaign`, `/validate` endpoints

4. **Fix `web_scrape` SSRF** — block requests to private IP ranges

5. **Fix `personas.html` API calls** — route through backend or add API key input

### Short-Term (Before Selling)

6. **Connect persistence** — replace in-memory `campaigns` dict with Supabase
7. **Implement `store_data`/`read_data`** tools for real persistence
8. **Add rate limiting** on all endpoints
9. **Pin dependency versions** in `requirements.txt`
10. **Load `.env` file** — add `load_dotenv()` to `config.py` or remove `python-dotenv`
11. **Add basic tests** — engine loop, provider failover, tool execution
12. **Fix `datetime.utcnow`** deprecation warnings

### Medium-Term (Production Quality)

13. **Move frontend to a build system** (Vite + React) — eliminate Babel overhead
14. **Add structured logging** (JSON format for log aggregation)
15. **Add error monitoring** (Sentry)
16. **Add CI/CD** (GitHub Actions: lint, test, deploy)
17. **Tighten CORS** to specific domains
18. **Add Supabase database migrations** for schema defined in BLUEPRINT
19. **Add session refresh** logic in frontend for Supabase tokens

---

## 9. WHAT'S ACTUALLY GOOD

This audit is critical by design, but the codebase has genuine strengths worth highlighting:

- **Provider failover is production-grade** — exponential backoff, cooldowns, error counting, normalized tool calling across 3 providers. This is better than most production codebases.
- **ReAct engine is clean** — proper tool_use/tool_result message threading, streaming, timeout enforcement.
- **Tool registry is extensible** — adding new tools is a single `registry.register()` call.
- **Agent configs are data-driven** — adding a new agent is a single `AgentConfig()` call.
- **Persona engine is impressive** — 8 deeply psychological personas with cognitive biases, wounds, and contradictions. Not toy personas.
- **BLUEPRINT is comprehensive** — clear build order, phased approach, specific implementation details.

The foundation is strong. The gaps are mostly about deployment, persistence, and security — not architecture.

---

*Generated by full repository audit on 2026-03-20*
