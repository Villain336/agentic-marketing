# SUPERVISOR — Complete Build Blueprint
# For Claude Code: Read this entire document before writing any code.
# This is the master specification for building the Supervisor autonomous agency platform.

---

## WHAT THIS IS

Supervisor is an autonomous agentic marketing agency SaaS. Users sign up, describe their business idea, go through extensive AI-assisted onboarding, and get a fully operational business with 12+ AI agents that prospect, outreach, create content, run ads, handle clients, launch sites, manage legal, GTM, email, PPC — all autonomously with multi-provider LLM failover.

The vision: Shopify for agentic businesses. The human provides the idea and entrepreneurial judgment. The agents do everything else.

---

## WHAT EXISTS ALREADY (DO NOT REBUILD)

The following files are already built, tested, and verified. They live in the repo under `backend/` and `frontend/`. Start from these.

### Backend (Python/FastAPI) — `backend/`
- `config.py` — Environment settings, 3-provider priority chain (Anthropic → OpenAI → Google)
- `models.py` — Pydantic models: tools, agents, campaigns, API contracts, SSE events
- `providers.py` — Anthropic/OpenAI/Google adapters with auto-failover, exponential backoff, streaming, tool calling normalized across all three
- `tools.py` — Tool registry + 8 built-in tools (web_search, web_scrape, company_research, find_contacts, verify_email, analyze_website, store_data, read_data)
- `engine.py` — ReAct agentic reasoning loop: Plan → Act (call tool) → Observe (read result) → Decide (loop or finish). Streams every step as SSE
- `agents.py` — All 12 agent configurations with system prompts, tool access categories, memory extractors
- `main.py` — FastAPI with SSE streaming: POST /agent/{id}/run, POST /campaign/run, GET /health, GET /agents, POST /validate
- `Dockerfile` — Ready for Railway/Fly.io deployment
- `.env.example` — All env vars documented

### Frontend (React CDN) — `frontend/`
- `index.html` — Full app: landing page, auth (Supabase), Stripe checkout (3 tiers: $2500/$7000/$15000), onboarding (5 steps), provisioning animation, dashboard with 12-agent pipeline, output viewer, grading, campaign memory, log panel, brand training. Already wired to backend with try-backend-first/fallback-to-direct-API pattern. Backend status indicator in dashboard header.
- `personas.html` — Standalone buyer persona simulation engine. 8 deep personas with psychological profiles, 8 market contexts, 8 test types, batch testing, individual chat, subject line testing, AI-generated insights, test history tracking.

### Infrastructure
- Supabase project exists with auth configured (email/password)
- Stripe products/prices exist for 3 tiers with payment links
- All 12 agents have consistent copy across landing, pricing, dashboard, and memory tracking

---

## PHASE 1: DEPLOY & VALIDATE (Do this first)

### 1.1 Deploy backend to Railway
- Push repo to GitHub
- Connect to Railway
- Set environment variables from .env.example (minimum: ANTHROPIC_API_KEY)
- Backend URL will be something like supervisor-api.up.railway.app
- Update frontend `API_URL` — change the else branch from "/api" to the Railway URL:
  ```javascript
  const API_URL = window.location.hostname === "localhost" ? "http://localhost:8000" : "https://supervisor-api.up.railway.app";
  ```

### 1.2 Validate end-to-end
- Sign up through the frontend
- Complete onboarding
- Run a single agent (Prospector) and confirm backend SSE streaming works
- Verify the dashboard shows real-time tool calls (web_search, company_research, etc.)
- Verify fallback works: stop the backend, run an agent, confirm it falls back to direct Anthropic call
- Verify /health endpoint shows provider status

### 1.3 Add SERPER_API_KEY for real web search
- Sign up at serper.dev (free tier: 2500 searches)
- Add to Railway env vars
- Verify Prospector agent actually searches the web and returns real companies

### 1.4 Add APOLLO_API_KEY for real lead enrichment (optional but high impact)
- Apollo.io free tier gives 10,000 credits/month
- Enables company_research and find_contacts tools with real data
- Prospector goes from "researching via web search" to "pulling verified firmographic data and decision-maker emails"

---

## PHASE 2: EXTENSIVE ONBOARDING (The core differentiator)

The current onboarding is 5 text inputs. Replace it with a 7-stage AI-assisted business creation experience. This is the highest-impact feature to build next because it determines the quality of everything agents produce.

### 2.1 Stage 1: Vision Interview (AI Conversation)

Replace the current step-by-step form with an AI chat interface.

**Implementation:**
- New React component: `<VisionInterview />`
- Uses the backend `/agent/vision_interview/run` endpoint (new agent to create)
- The AI asks open-ended questions, extracts structured business data from the conversation
- Conversation format: user types freely, AI responds with follow-up questions
- After 10-15 exchanges, AI presents a structured Business Brief for confirmation
- User can edit any field before proceeding

**The Vision Interview agent (add to agents.py):**
```
id: "vision_interview"
role: "Business Strategist"
tools: ["web_search"] (to validate market claims in real time)
```

System prompt core:
```
You are a world-class business strategist conducting a discovery interview.
Ask open-ended questions. Extract: service definition, value proposition,
ICP (firmographic + psychographic), competitive positioning, founder's
unfair advantage, initial pricing hypothesis.

Start with: "Tell me about the business you want to build."
Follow up with specific questions based on what they say.
After 10-15 exchanges, present a structured Business Brief.

NEVER ask generic questions. Every follow-up should be specific to what
the human just said. If they say "bookkeeping for Shopify stores" — ask
about which segment of Shopify stores, what specific pain points, whether
they have bookkeeping experience, what their pricing model would be.
```

**Output: BusinessBrief object**
```python
class BusinessBrief(BaseModel):
    name: str
    service_definition: str
    value_proposition: str
    icp_firmographic: str  # company size, industry, revenue, location
    icp_psychographic: str  # pain points, desires, buying behavior
    competitive_positioning: str
    founder_advantage: str
    pricing_hypothesis: str
    conversation_transcript: str  # for future reference
```

### 2.2 Stage 2: Mood Board (Visual DNA Capture)

**Implementation:**
- New React component: `<MoodBoard />`
- Three input methods:
  1. URL paste → backend crawls page, takes screenshot via Puppeteer/Playwright, extracts visual signals via vision model
  2. Image upload → stored, analyzed by vision model
  3. Search/browse → backend searches for examples in the industry, user swipes yes/no
- Each reference is analyzed and the system extracts: color palette, typography style, layout density, photography direction, overall vibe
- Real-time clustering: as user adds references, the AI identifies patterns and presents them: "You gravitate toward dark backgrounds, high contrast, minimal illustration, photography-forward..."
- User confirms or corrects the visual analysis

**New backend endpoints:**
```
POST /onboarding/crawl-url
  - Input: { url: string }
  - Uses Puppeteer (headless Chrome) or Playwright to screenshot the page
  - Runs screenshot through vision model (Claude with vision or GPT-4o) to extract:
    - Dominant colors (hex values)
    - Typography classification (serif/sans-serif/mono, weight, size scale)
    - Layout pattern (grid/freeform, density, whitespace ratio)
    - Photography style (lifestyle/product/abstract/illustration/none)
    - Overall vibe keywords
  - Returns: { screenshot_url, analysis: VisualAnalysis }

POST /onboarding/analyze-image
  - Input: uploaded image file
  - Same vision model analysis
  - Returns: { analysis: VisualAnalysis }

POST /onboarding/search-references
  - Input: { query: string, industry: string }
  - Uses web_search + web_scrape to find example sites
  - Screenshots each one
  - Returns array of { url, screenshot_url, analysis }

POST /onboarding/generate-visual-dna
  - Input: { references: VisualAnalysis[] }
  - AI clusters all references, identifies patterns, generates complete Visual DNA Profile
  - Returns: VisualDNA object
```

**Output: VisualDNA object**
```python
class VisualDNA(BaseModel):
    color_palette: dict  # primary, secondary, accent, neutrals (hex values)
    typography: dict  # display_font, body_font, mono_font, size_scale
    photography_direction: str  # e.g. "Natural lifestyle photography of real people in bright workspaces. Avoid: stock photos, calculators, generic office settings"
    illustration_style: str  # e.g. "Minimal line illustrations" or "None — photography only"
    layout_preferences: str  # e.g. "Generous whitespace, asymmetric grid, content-first"
    density: str  # sparse / balanced / dense
    brand_personality: str  # e.g. "Premium consultancy — sophisticated, trustworthy, modern without being trendy"
    anti_patterns: list[str]  # things to NEVER do
    reference_urls: list[str]
    competitor_urls: list[str]  # separated from aspirational references
```

**Crawler infrastructure:**
- Use Cloudflare Browser Rendering API (https://developers.cloudflare.com/browser-rendering/) if on Cloudflare
- Or run Playwright in a Docker sidecar on Railway
- Or use a screenshot API service like ScreenshotOne, Urlbox, or Browserless
- Cache screenshots in Supabase Storage or Cloudflare R2

### 2.3 Stage 3: Business Formation (Legal Setup)

**Implementation:**
- New React component: `<BusinessFormation />`
- AI-guided flow: entity type recommendation → state selection → filing → EIN → banking → insurance
- Each step has AI explanation specific to the user's business

**Integration options (pick one per category):**
- Entity formation: Stripe Atlas API, Northwest Registered Agent API, or manual guided flow with links
- EIN: IRS online application (manual step — AI pre-fills and guides)
- Banking: Mercury API (programmatic account opening), or Relay, or manual with pre-filled application
- Insurance: Coverwallet API, Next Insurance API, or guided comparison

**For MVP:**
- Don't auto-file. Generate the complete filing checklist with pre-filled information and direct links.
- The Legal agent runs during this stage and produces the entity structure recommendation, required documents list, and compliance checklist specific to their state + service type.
- Save all formation data to the BusinessProfile.

**Output: FormationProfile object**
```python
class FormationProfile(BaseModel):
    entity_type: str  # LLC, S-Corp, etc.
    state_of_formation: str
    registered_agent: str
    ein: str  # filled later
    bank_name: str
    bank_account_status: str  # pending / active
    insurance_types: list[str]
    insurance_status: str
    legal_checklist: str  # from Legal agent
```

### 2.4 Stage 4: Revenue Architecture

**Implementation:**
- New React component: `<RevenueArchitecture />`
- AI builds a financial model through conversation
- Covers: target client count (30/60/90 day), pricing strategy, revenue milestones, budget allocation
- Runs Persona Gauntlet on pricing in real time: "Let me test your pricing against 3 simulated buyers..."
- Displays persona reactions inline

**Backend:**
- Use existing `/validate` endpoint to test pricing against personas
- Add new endpoint or extend vision_interview agent for financial modeling

**Output: RevenueModel object**
```python
class RevenueModel(BaseModel):
    pricing_model: str  # monthly retainer, per-project, hybrid
    price_point: str
    target_clients_30d: int
    target_clients_90d: int
    target_revenue_90d: float
    target_revenue_year1: float
    startup_capital: float
    budget_allocation: dict  # { ads: 2000, tools: 500, domain: 200, reserve: 2300 }
    persona_pricing_feedback: str  # from gauntlet test
```

### 2.5 Stage 5: Channel Setup

**Implementation:**
- New React component: `<ChannelSetup />`
- Domain selection: Site Launch agent recommends 3, user picks, purchased via API
- Email: Google Workspace or Zoho provisioning
- Social: Platform recommendations based on ICP, bio/profile generation, OAuth connection
- CRM: HubSpot free tier setup with pipeline configured
- Payments: Stripe Connect onboarding

**Integrations:**
- Domain: Cloudflare Registrar API or Namecheap API
- Email: Google Workspace reseller API or manual guided setup
- Social: Twitter API v2 OAuth, LinkedIn OAuth
- CRM: HubSpot API (create account, configure pipeline)
- Payments: Stripe Connect onboarding link

**For MVP:**
- Domain: AI recommends, user purchases manually (provide direct links)
- Email: guided setup with pre-filled info
- Social: generate bios/profiles, user creates accounts and connects OAuth
- CRM: auto-provision HubSpot via API if possible, otherwise guided
- Payments: Stripe Connect link

### 2.6 Stage 6: Target Market Deep Dive

**Implementation:**
- New React component: `<MarketDeepDive />`
- This stage actually runs agents during onboarding
- Marketing Expert agent researches competitors (using URLs from mood board + web search)
- Prospector does a preliminary search to validate prospect volume
- Content agent identifies content gaps
- User watches agents work in real time (reuse dashboard SSE streaming)
- Results presented as: competitive landscape map, market size estimate, differentiation recommendation, content gap analysis

**Backend:**
- Use existing `/agent/{id}/run` endpoints
- Run marketing_expert, prospector (limited to 3 prospects), and content agent with lightweight configs
- New endpoint: `POST /onboarding/market-research` that orchestrates all three

### 2.7 Stage 7: Autonomy Configuration

**Implementation:**
- New React component: `<AutonomyConfig />`
- User selects autonomy level per agent category:
  - Full autonomy: agents act without approval
  - Guided autonomy: agents queue outputs for approval before external actions
  - Collaborative: human approves everything for first month, then system recommends loosening

**Output: AutonomyConfig object**
```python
class AutonomyConfig(BaseModel):
    global_level: str  # full / guided / collaborative
    per_agent_overrides: dict[str, str]  # agent_id → level
    spending_approval_threshold: float  # auto-approve below this
    outbound_approval_required: bool  # emails, social, ads
    content_approval_required: bool
    escalation_channel: str  # telegram / slack / email
```

### 2.8 Onboarding Data Model

All 7 stages produce a combined `OnboardingProfile` that becomes the master context for all agents:

```python
class OnboardingProfile(BaseModel):
    business_brief: BusinessBrief
    visual_dna: VisualDNA
    formation: FormationProfile
    revenue_model: RevenueModel
    channels: dict  # connected platforms and credentials
    market_research: dict  # competitive landscape, content gaps
    autonomy: AutonomyConfig
    mood_board_references: list[str]  # URLs
    mood_board_images: list[str]  # storage paths
    created_at: datetime
```

Store this in Supabase. Every agent reads from it. This replaces the current simple `BusinessProfile` model.

---

## PHASE 3: DESIGN AGENT (13th Agent)

### 3.1 Create the Design Agent

Add to `agents.py`:

```
id: "design"
label: "Design Director"
role: "Brand System & Visual QA"
icon: "◈"
tool_categories: ["web"]  # for competitor visual analysis
tier: Tier.STANDARD
max_iterations: 10
```

The Design Agent runs immediately after onboarding completes and before any other agents. It takes the VisualDNA from onboarding and produces a complete Brand System.

System prompt core:
```
You are a senior creative director with 15 years at top agencies.
You have the user's Visual DNA profile (their preferences, references, anti-patterns).

Produce a complete Brand System:

1. COLOR SYSTEM
   - Primary: hex + usage rules
   - Secondary: hex + usage rules
   - Accent: hex + usage rules
   - Neutrals: 5-shade scale from dark to light
   - Semantic: success, warning, error, info colors
   - Background: primary and secondary background colors
   - Text: primary, secondary, muted text colors

2. TYPOGRAPHY SYSTEM
   - Display font: name (from Google Fonts), weights, usage
   - Body font: name, weights, usage
   - Mono font: name, usage
   - Size scale: xs through 4xl with px values
   - Line height rules
   - Letter spacing rules for uppercase text

3. SPACING SYSTEM
   - Base unit and scale (4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px, 96px)
   - Component padding rules
   - Section margin rules
   - Content max-width

4. COMPONENT PATTERNS
   - Button styles: primary, secondary, ghost (with exact CSS)
   - Card styles: with exact border, radius, shadow, padding
   - Input styles
   - Navigation pattern
   - Hero section pattern
   - CTA section pattern

5. PHOTOGRAPHY/IMAGE DIRECTION
   - Detailed description of image style
   - Keywords for image search/generation
   - What to avoid

6. ANTI-PATTERNS
   - Specific things this brand must never do visually
   - Common mistakes for this industry

Output as structured JSON so other agents can consume it programmatically.
```

### 3.2 Visual QA Gate

Add a vision-model review step to every agent that produces visual output:

**In engine.py, add a post-processing hook:**

After Site Launch, Ads, Social, and Newsletter agents complete, the Design Agent reviews their output:

```python
async def visual_qa(agent_output: str, brand_system: dict, agent_id: str) -> dict:
    """Run visual QA on agent output using vision model."""
    # If the output contains code/HTML, render it and screenshot
    # Send screenshot + brand system to vision model
    # Get critique and score
    # If score < threshold, feed critique back and re-run agent
```

For MVP: skip screenshot rendering. Just have the Design Agent review the text output (site copy, ad copy, email design) for brand consistency.

---

## PHASE 4: EXECUTION TOOLS

These tools make agents DO things, not just plan things.

### 4.1 Email Sending (Priority 1)

Add to `tools.py`:
```python
# Tool: send_email
# Uses SendGrid API
# Inputs: to, subject, body, from_name, reply_to
# Returns: { sent: true, message_id: "xxx" }
# Safety: rate limited to 50/day per campaign, requires approval if autonomy is "guided"

# Tool: schedule_email_sequence
# Inputs: emails[] with { to, subject, body, send_at }
# Creates scheduled sends in SendGrid
# Returns: { scheduled: true, count: 3, send_dates: [...] }

# Tool: check_email_status
# Inputs: message_id
# Returns: { delivered: true, opened: false, clicked: false }
```

**Webhook receiver endpoint:**
```
POST /webhooks/sendgrid
- Receives open/click/reply/bounce events
- Updates campaign memory with engagement data
- Triggers Outreach agent re-evaluation if reply rate drops below threshold
```

### 4.2 Social Media Posting

Add to `tools.py`:
```python
# Tool: post_twitter
# Uses Twitter API v2
# Inputs: text, media_ids (optional)
# Safety: max 10 posts/day, content goes through brand voice check

# Tool: reply_twitter
# Inputs: tweet_id, text
# Safety: max 20 replies/day, mandatory tone check, topic boundary enforcement

# Tool: search_twitter
# Inputs: query, max_results
# Returns relevant tweets for engagement opportunities

# Tool: post_linkedin
# Uses LinkedIn API
# Inputs: text, image_url (optional)
# Safety: max 2 posts/day
```

**Twitter conversation engine:**
- Background job runs every 15 minutes
- Searches for relevant conversations using ICP keywords
- Social agent evaluates each conversation: relevant? safe to engage? what value can we add?
- Drafts replies, runs through quality gates (brand voice, topic boundaries, tone)
- Posts approved replies
- Handles incoming DMs: qualifies interest, routes to Outreach agent or books calls

**Quality gates for social:**
1. Topic boundary check: is this within our expertise area?
2. Sentiment check: is this a safe conversation to enter? (no controversies, arguments, pile-ons)
3. Brand voice check: does this sound like our founder persona?
4. Bot detection avoidance: vary reply timing, don't use identical phrases, mix engagement types

### 4.3 Ad Deployment

Add to `tools.py`:
```python
# Tool: create_meta_ad_campaign
# Uses Meta Marketing API
# Inputs: campaign_name, daily_budget, targeting, ad_creatives[]
# Returns: { campaign_id, status: "draft" }
# Safety: requires human approval on first campaign, auto-approve subsequent if budget < threshold

# Tool: create_google_ads_campaign
# Uses Google Ads API
# Inputs: campaign_name, daily_budget, keywords, ad_copy
# Returns: { campaign_id, status: "draft" }

# Tool: get_ad_performance
# Inputs: campaign_id, platform, date_range
# Returns: { impressions, clicks, ctr, cpa, conversions, spend }

# Tool: update_ad_budget
# Inputs: campaign_id, platform, new_daily_budget
# Safety: max 2x increase per adjustment, max $500/day without human approval
```

### 4.4 Site Deployment

Add to `tools.py`:
```python
# Tool: generate_site_code
# Inputs: brand_system, site_brief, page_content
# Uses Claude/GPT to generate React + Tailwind code
# Returns: { files: { "index.html": "...", "styles.css": "..." } }

# Tool: deploy_to_vercel
# Uses Vercel API
# Inputs: project_name, files, domain
# Returns: { url, deployment_id, status }

# Tool: deploy_to_cloudflare
# Uses Cloudflare Workers/Pages API
# Alternative to Vercel

# Tool: purchase_domain
# Uses Cloudflare Registrar API
# Inputs: domain_name
# Safety: requires human approval
# Returns: { purchased: true, domain, nameservers }

# Tool: configure_dns
# Inputs: domain, records[]
# Returns: { configured: true }
```

### 4.5 CRM Integration

Add to `tools.py`:
```python
# Tool: create_crm_contact
# Uses HubSpot API
# Inputs: name, email, company, title, source, notes
# Returns: { contact_id }

# Tool: update_deal_stage
# Inputs: deal_id, stage
# Returns: { updated: true }

# Tool: log_activity
# Inputs: contact_id, type (email/call/meeting), notes, date
# Returns: { activity_id }

# Tool: get_pipeline_summary
# Returns: { stages: [{ name, count, value }], total_pipeline_value }
```

### 4.6 Calendar Booking

```python
# Tool: create_booking_link
# Uses Cal.com API
# Inputs: event_type, duration, availability
# Returns: { booking_url }

# Tool: send_booking_link
# Inputs: contact_email, booking_url, message
# Combines email sending with booking link
```

---

## PHASE 5: SENSING & FEEDBACK LOOP

### 5.1 Webhook Receiver

Add to `main.py`:
```python
@app.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    """
    Universal webhook receiver.
    Sources: sendgrid, stripe, hubspot, twitter, meta_ads, google_ads
    Routes events to campaign memory and triggers agent re-evaluation.
    """
```

### 5.2 Performance Data Ingestion

New file: `sensing.py`
```python
class SensingEngine:
    """Ingests performance data and updates campaign memory."""

    async def process_email_event(self, event):
        # Update: email open rates, reply rates, bounce rates per variant
        # Trigger: if reply_rate < 2% for 3 days → re-run Outreach agent

    async def process_ad_event(self, event):
        # Update: CPA, CTR, ROAS per campaign/variant
        # Trigger: if CPA > target for 7 days → PPC agent re-optimizes

    async def process_site_event(self, event):
        # Update: traffic, bounce rate, conversion rate, traffic sources
        # Trigger: if bounce_rate > 70% → Content agent reviews page

    async def process_crm_event(self, event):
        # Update: pipeline value, close rates, deal velocity
        # Trigger: if pipeline drops 20% → Prospector runs additional batch

    async def process_social_event(self, event):
        # Update: engagement rates, follower growth, best performing content types
        # Trigger: weekly summary → Social agent adjusts content mix
```

### 5.3 Agent Performance Scoring

New file: `scoring.py`
```python
class AgentScorer:
    """Scores agents on actual business outcomes, not output quality."""

    def score_prospector(self, campaign) -> float:
        # % of prospects that became meetings
        # Quality: ICP match accuracy

    def score_outreach(self, campaign) -> float:
        # Reply rate, positive reply rate, meetings booked per sequence sent

    def score_content(self, campaign) -> float:
        # Organic traffic generated, time on page, leads from content

    def score_social(self, campaign) -> float:
        # Engagement rate, follower growth, DM conversations started

    def score_ads(self, campaign) -> float:
        # CPA vs target, ROAS, conversion rate

    def score_cs(self, campaign) -> float:
        # Client retention rate, NPS if available, upsell rate

    # Returns letter grade (A+ through F) with specific reasoning
```

---

## PHASE 6: SUPERVISOR META-AGENT

### 6.1 The Real Supervisor

New agent in `agents.py`:
```
id: "supervisor"
label: "Supervisor"
role: "Chief Operating Officer"
icon: "◎"
tool_categories: ["web", "memory", "prospecting"]  # can access all tools
tier: Tier.STRONG  # uses best model available
max_iterations: 25
```

The Supervisor runs on a schedule (weekly) and on triggers (performance drops, milestones hit, human requests via Telegram/Slack).

System prompt core:
```
You are the COO of an autonomous marketing agency. You oversee 12 specialist agents.

You have access to:
- Full campaign memory (all agent outputs and performance data)
- Agent performance scores (outcome-based, not output-based)
- Budget allocation and spend tracking
- Revenue attribution data

Your responsibilities:
1. WEEKLY REVIEW: Analyze all agent performance. Identify wins, risks, and opportunities.
2. REALLOCATION: Recommend budget shifts between channels based on performance.
3. RE-RUNS: Decide which agents need to re-run with updated strategies.
4. ESCALATION: Flag decisions that require human judgment (with your recommendation).
5. BRIEFING: Generate a concise executive summary for the human owner.

Format your weekly briefing as:
## This Week's Results
[key metrics with trends]

## What's Working
[top 2-3 wins with specific data]

## What Needs Attention
[top 2-3 risks with recommended actions]

## My Recommendations
[specific actions I want to take, with reasoning]

## Needs Your Input
[decisions only the human can make]
```

### 6.2 Agent Debate Protocol

Before campaign outputs finalize, agents review each other's work.

**Implementation:**
New endpoint: `POST /campaign/{id}/debate`
- Marketing Expert reviews Outreach messaging for positioning alignment
- Content agent reviews Ads copy for brand voice consistency
- Design agent reviews all visual outputs for Brand System compliance
- Prospector validates that ICP targeting is tight enough across all agents

Each reviewer produces: { approved: bool, issues: string[], suggested_changes: string[] }
If any reviewer flags critical issues, the original agent re-runs with the feedback.

---

## PHASE 7: AGENT WALLET & FINANCIAL INFRASTRUCTURE

### 7.1 Budget Management

New file: `wallet.py`
```python
class AgentWallet:
    """Manages per-agent budget allocations and spend tracking."""

    async def allocate_budget(self, campaign_id, agent_id, amount, period):
        # Set weekly/monthly budget for an agent

    async def request_spend(self, campaign_id, agent_id, amount, description) -> bool:
        # Returns True if within budget, False if needs approval
        # Logs every spend request

    async def record_spend(self, campaign_id, agent_id, amount, tool, description):
        # Record actual spend with full attribution

    async def get_balance(self, campaign_id, agent_id) -> dict:
        # Current budget remaining, total spent, ROI if measurable

    async def reallocate(self, campaign_id, from_agent, to_agent, amount):
        # Move budget between agents (Supervisor meta-agent does this)
```

### 7.2 Revenue Tracking

```python
class RevenueTracker:
    """Tracks revenue and attributes it to agent actions."""

    async def record_revenue(self, campaign_id, amount, client_id, source_agent):
        # Which agent's output led to this revenue?

    async def get_attribution(self, campaign_id) -> dict:
        # { outreach: 73%, content: 18%, ads: 9% }

    async def get_roi_by_agent(self, campaign_id) -> dict:
        # { prospector: { spend: 0, attributed_revenue: 45000 },
        #   ads: { spend: 3200, attributed_revenue: 8500, roi: 2.65x } }
```

---

## PHASE 8: MESSAGING INTEGRATION (Telegram/Slack)

### 8.1 Telegram Bot

New file: `integrations/telegram.py`
```python
# Uses python-telegram-bot library
# The Supervisor meta-agent is accessible via Telegram

# Commands:
# /status — campaign performance summary
# /pause {agent} — pause an agent
# /resume {agent} — resume
# /briefing — get this week's executive briefing
# /approve {id} — approve a queued action
# /spend — show budget/spend summary

# Natural language:
# "How are ads performing?" → Supervisor answers with data
# "Pause all outreach" → executes and confirms
# "The client loved the proposal, close the deal" → CS agent updates, CRM updated

# Notifications (push to user):
# New client signed, revenue milestone, performance alerts, approval requests
```

### 8.2 Slack Integration

Same as Telegram but via Slack bot. Use Slack Bolt (Python).
Commands work as slash commands. Natural language works in a DMs channel with the bot.

---

## PHASE 9: MULTI-CAMPAIGN & CLIENT MANAGEMENT

### 9.1 Portfolio Dashboard

- New frontend view: shows all active campaigns as cards
- Each card: business name, revenue, agent status (traffic light), key metrics
- Click through to individual campaign dashboard (existing)

### 9.2 Cross-Campaign Learning (Campaign Genome)

New file: `genome.py`
```python
class CampaignGenome:
    """Stores and queries structured campaign intelligence across all users."""

    async def record_campaign_dna(self, campaign):
        # Extract: ICP type, service type, geography, channels used,
        # messaging angles, actual outcomes, what worked, what didn't

    async def query_intelligence(self, icp_type, service_type, geography) -> dict:
        # "For B2B SaaS targeting mid-market in North America,
        #  the average reply rate is 4.2%, best performing subject lines
        #  are question-based, optimal email send time is Tuesday 9am"

    async def get_recommendations(self, new_campaign) -> dict:
        # Based on similar campaigns, recommend: channels, messaging, timing
```

### 9.3 Client Portal (White-Label)

- Separate frontend route: /client/{client_id}
- Shows: campaign performance, content calendar, recent activity
- Branded with the AGENCY's brand (from onboarding), not Supervisor's brand
- Read-only for clients. Approval workflows for content/ads.

---

## PHASE 10: SELF-ORGANIZING AGENTS

### 10.1 Agent Lifecycle Management

New file: `lifecycle.py`
```python
class AgentLifecycle:
    """Manages agent creation, evaluation, evolution, and dissolution."""

    async def evaluate_all(self, campaign_id):
        # Score every agent on outcome-based metrics
        # Flag underperformers (below threshold for 3+ weeks)

    async def recommend_action(self, agent_id, score_history) -> str:
        # "retune" — adjust prompts/strategy
        # "ab_test" — spin up variant, run both
        # "specialize" — split into 2 agents for different verticals
        # "dissolve" — remove agent, reallocate resources
        # "hire" — bring in marketplace agent

    async def spawn_variant(self, agent_id, modifications: dict):
        # Create a copy of agent with different config
        # Run in parallel for 2 weeks
        # Promote winner, dissolve loser

    async def dissolve_agent(self, campaign_id, agent_id):
        # Gracefully shut down: pause all scheduled actions,
        # save final state, reallocate budget, notify Supervisor
```

---

## PHASE 11: PERSONA GAUNTLET INTEGRATION

### 11.1 Merge Persona Engine Into Backend

The persona engine currently lives as a standalone HTML file. Move the core logic server-side.

New file: `gauntlet.py`
```python
# Port all 8 personas from personas.html into Python
# Port the system prompt builder, analysis functions
# Add as a quality gate in the agent engine

class PersonaGauntlet:
    async def validate(self, output: str, icp: str, test_type: str) -> GauntletResult:
        # Run output against 3-5 personas matching the ICP
        # Return: fit_score, per_persona_reactions, top_objections, recommended_changes

    async def gate_check(self, agent_id: str, output: str, campaign: Campaign) -> bool:
        # If fit_score > 60: pass
        # If fit_score 40-60: pass with warnings logged
        # If fit_score < 40: fail — agent must rewrite

# Integrate into engine.py:
# After agent produces final output, before marking "done":
# if agent_id in OUTBOUND_AGENTS:  # outreach, social, ads, newsletter
#     result = await gauntlet.gate_check(agent_id, output, campaign)
#     if not result.passed:
#         # Feed critique back, re-run agent
```

---

## DATABASE SCHEMA (Supabase)

```sql
-- Core tables (extend existing)
CREATE TABLE onboarding_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    business_brief JSONB,
    visual_dna JSONB,
    formation JSONB,
    revenue_model JSONB,
    channels JSONB,
    market_research JSONB,
    autonomy_config JSONB,
    mood_board_urls TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    profile_id UUID REFERENCES onboarding_profiles(id),
    status TEXT DEFAULT 'active',
    memory JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    agent_id TEXT NOT NULL,
    agent_label TEXT,
    status TEXT,
    steps JSONB DEFAULT '[]',
    output TEXT,
    memory_extracted JSONB DEFAULT '{}',
    provider_used TEXT,
    model_used TEXT,
    iterations INT,
    duration_ms INT,
    score FLOAT,
    grade TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE agent_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    agent_id TEXT NOT NULL,
    allocated NUMERIC DEFAULT 0,
    spent NUMERIC DEFAULT 0,
    period TEXT DEFAULT 'monthly',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE spend_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    agent_id TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    tool TEXT,
    description TEXT,
    approved_by TEXT,  -- 'auto' or 'human' or 'supervisor'
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE revenue_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    amount NUMERIC NOT NULL,
    client_id TEXT,
    source_agent TEXT,
    attribution_chain JSONB,  -- full touchpoint history
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE performance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    source TEXT,  -- sendgrid, meta_ads, google_ads, hubspot, twitter, analytics
    event_type TEXT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE campaign_genome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    icp_type TEXT,
    service_type TEXT,
    geography TEXT,
    channel_mix JSONB,
    messaging_angles JSONB,
    outcomes JSONB,  -- { reply_rate, cpa, close_rate, etc. }
    lessons JSONB,   -- { what_worked, what_didnt }
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE brand_systems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    color_palette JSONB,
    typography JSONB,
    photography_direction TEXT,
    layout_preferences TEXT,
    anti_patterns TEXT[],
    full_system JSONB,  -- complete Design Agent output
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE approval_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    agent_id TEXT,
    action_type TEXT,  -- send_email, post_social, deploy_ad, deploy_site, spend
    content JSONB,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    decided_by TEXT,  -- human, supervisor, auto
    created_at TIMESTAMPTZ DEFAULT now(),
    decided_at TIMESTAMPTZ
);
```

---

## BUILD ORDER (Execute in this sequence)

1. Deploy existing backend to Railway, validate end-to-end
2. Add Serper + Apollo API keys, verify real tool results
3. Build Stage 1 onboarding (Vision Interview) — highest leverage change
4. Build Stage 2 onboarding (Mood Board) — requires crawler infrastructure
5. Build Design Agent (13th agent) + Brand System generation
6. Build Stage 4 onboarding (Revenue Architecture with Persona Gauntlet pricing test)
7. Build Stages 3, 5, 6, 7 onboarding (formation, channels, market research, autonomy)
8. Build email sending tool + SendGrid webhook receiver
9. Build Supervisor meta-agent with weekly briefing
10. Build Telegram bot integration
11. Build Twitter conversation engine (Social agent replies)
12. Build ad deployment tools (Meta + Google APIs)
13. Build site deployment tool (Vercel API)
14. Build CRM integration (HubSpot)
15. Build agent performance scoring (outcome-based)
16. Build Persona Gauntlet as quality gate in engine
17. Build agent wallet + budget management
18. Build revenue attribution tracking
19. Build multi-campaign portfolio dashboard
20. Build Campaign Genome (cross-campaign learning)
21. Build agent lifecycle management (spawn/dissolve/A-B test)
22. Build client portal (white-label)

Each item is a Claude Code session. Items 1-6 get you to a fundable demo. Items 1-12 get you to a product you can sell. Items 1-22 get you to the full vision.

---

## CRITICAL RULES FOR CLAUDE CODE

1. Never rebuild what already exists. Read the existing files first.
2. All new backend code goes in `backend/`. All new frontend code goes in `frontend/`.
3. Every new tool follows the registry pattern in `tools.py` — register name, description, parameters, handler, category.
4. Every new agent follows the AgentConfig pattern in `agents.py`.
5. All external API calls go through tools, never hardcoded in agent prompts.
6. All LLM calls go through the model router in `providers.py`, never direct to a provider.
7. SSE streaming for all long-running operations. Never block the frontend.
8. Every agent action that touches the external world (sends email, posts social, spends money) must check the autonomy config and route through the approval queue if required.
9. Every spend must be logged to spend_log with full attribution.
10. Test each phase end-to-end before moving to the next.
