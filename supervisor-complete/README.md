# Supervisor — Autonomous Agency Platform

An autonomous agentic marketing agency SaaS. 12 AI agents prospect, outreach, create content, run ads, handle clients, launch sites, and manage legal, GTM, email, and PPC — in a closed loop with multi-provider failover.

## Structure

```
supervisor/
├── backend/          # FastAPI orchestration layer
│   ├── config.py     # Environment settings, provider chain
│   ├── models.py     # Pydantic models for everything
│   ├── providers.py  # Anthropic/OpenAI/Google adapters + failover router
│   ├── tools.py      # Tool registry + 8 built-in tools
│   ├── engine.py     # Agentic reasoning loop (ReAct pattern)
│   ├── agents.py     # All 12 agent configurations
│   ├── main.py       # FastAPI app with SSE streaming
│   ├── .env.example  # Environment template
│   └── README.md     # Backend documentation
│
├── frontend/         # Client-side application
│   ├── index.html    # Main app (auth, onboarding, dashboard)
│   └── personas.html # Buyer persona simulation engine
│
└── README.md         # This file
```

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add at least ANTHROPIC_API_KEY
python main.py
```

### Frontend
Serve `frontend/` via any static server, or open `index.html` directly.
The frontend auto-detects backend availability and falls back to direct API calls.

## Tech Stack
- **Backend:** Python, FastAPI, httpx, Pydantic
- **Frontend:** React (CDN), Babel (CDN), vanilla JS
- **Auth:** Supabase Auth
- **Payments:** Stripe Checkout
- **LLM Providers:** Anthropic Claude, OpenAI GPT, Google Gemini (failover chain)
- **Tool APIs:** Apollo.io, Hunter.io, Serper.dev (optional enrichment)
