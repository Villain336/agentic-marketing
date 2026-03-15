# Supervisor — Backend Orchestration Layer

The server-side brain for the Supervisor autonomous agency platform. Replaces the client-side single-API-call architecture with a real agentic reasoning loop, multi-provider failover, and extensible tool system.

## Architecture

```
Frontend (index.html)
    ↓ SSE stream
FastAPI Server (main.py)
    ↓
Agent Engine (engine.py) — ReAct loop: Plan → Act → Observe → Decide
    ↓                 ↓
Model Router         Tool Registry
(providers.py)       (tools.py)
    ↓                 ↓
Anthropic → OpenAI → Google    Apollo · Hunter · Serper · Web Scraper
(automatic failover)            (extensible — add SendGrid, LinkedIn, etc.)
```

## What Changed From v0

| Before (client-side) | After (this backend) |
|---|---|
| Single API call per agent | Multi-step reasoning loop with tool use |
| Agents generate text only | Agents research, verify, and act using tools |
| Anthropic-only, crashes if down | 3-provider failover with exponential backoff |
| Fake prospect data (hallucinated) | Real companies via Apollo/Hunter/web scraping |
| No backend — browser makes API calls | FastAPI server holds keys, runs loops, streams SSE |
| 7 agents tracked in UI | All 12 agents with full memory tracking |

## Files

| File | Purpose |
|---|---|
| `config.py` | Environment settings, provider priority chain |
| `models.py` | Pydantic models — tools, agents, campaigns, API contracts |
| `providers.py` | Anthropic/OpenAI/Google adapters + failover router |
| `tools.py` | Tool registry + 8 built-in tools (web, prospecting, email, memory) |
| `engine.py` | The agentic reasoning loop (ReAct pattern) |
| `agents.py` | All 12 agent configurations with prompts and tool access |
| `main.py` | FastAPI app with SSE streaming endpoints |

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure (minimum: one LLM provider key)
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum

# 3. Run
python main.py
# → http://localhost:8000

# 4. Test
curl http://localhost:8000/health
curl http://localhost:8000/agents
```

## API Endpoints

### Status
- `GET /health` — Provider status, active campaigns
- `GET /agents` — List all 12 agents with tool counts
- `GET /providers` — LLM provider health and failover state

### Agent Execution (SSE streams)
- `POST /agent/{agent_id}/run` — Run single agent, returns SSE event stream
- `POST /campaign/run` — Run full 12-agent campaign loop

### Campaign Management
- `GET /campaign/{id}` — Campaign state and memory
- `GET /campaign/{id}/memory` — Memory snapshot
- `DELETE /campaign/{id}` — Delete campaign

### Validation
- `POST /validate` — Run agent output through persona simulation

## SSE Event Types

The frontend receives these events during agent execution:

```
status     — Agent starting, tool count
think      — Streamed text output (partial)
tool_call  — Agent invoking a tool (name + input)
tool_result — Tool execution result
output     — Final complete output + memory update
error      — Something failed
```

## Adding New Tools

```python
# In tools.py
async def _send_email(to: str, subject: str, body: str) -> str:
    # Your SendGrid/Resend implementation
    ...

registry.register("send_email", "Send an email via SendGrid",
    [ToolParameter(name="to", description="Recipient email"),
     ToolParameter(name="subject", description="Subject line"),
     ToolParameter(name="body", description="Email body")],
    _send_email, "email")
```

Then add `"email"` to any agent's `tool_categories` to give them access.

## Provider Failover

The router tries providers in priority order. On failure:
1. Logs the error
2. Applies exponential cooldown (5s → 15s → 45s → 120s max)
3. Tries the next provider
4. Frontend never sees a disruption

On success: resets that provider's error count and cooldown.

## 12 Agents

**Campaign Loop (7):** Prospector → Outreach → Content → Social → Ads → Client Success → Site Launch

**Operations Layer (5):** Legal → Marketing Expert → Procurement → Newsletter → PPC Manager

## Next Steps

1. **Connect frontend** — Replace `streamClaude()` calls with `fetch('/agent/{id}/run')` SSE
2. **Add execution tools** — SendGrid, LinkedIn API, Meta/Google Ads APIs, Vercel deploy
3. **Persist to Supabase** — Campaign state, agent runs, tool results
4. **Supervisor meta-agent** — Orchestrator that reviews all outputs and decides re-runs
5. **Persona gauntlet** — Auto-validate outputs before marking "done"
