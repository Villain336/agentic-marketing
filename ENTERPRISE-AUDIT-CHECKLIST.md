# Omni OS — Enterprise Production Audit

**Date:** 2026-03-20
**Scope:** Full-stack agentic SaaS platform (backend, infrastructure, financial controls)
**Method:** Code-level verification against established industry frameworks

---

## Frameworks Used

This audit maps the codebase against two established, peer-reviewed security frameworks:

1. **OWASP Top 10 for Agentic Applications 2026** (ASI-01 through ASI-10)
   — The industry-standard framework for autonomous AI agent security, published December 2025 by the OWASP GenAI Security Project. Developed by 100+ security experts.
   — Source: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

2. **OWASP Top 10 for LLM Applications 2025** (LLM01 through LLM10)
   — The standard for LLM-specific security risks in production applications.
   — Source: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/

Additionally referenced:
- **NIST AI Risk Management Framework (AI RMF 1.0)** — NIST AI 100-1, four functions: Govern, Map, Measure, Manage
- **OWASP LLM Applications Cybersecurity and Governance Checklist v1.1**
- **SOC 2 Trust Services Criteria** (Security, Availability, Processing Integrity, Confidentiality, Privacy)

---

## Part 1: Verification of Previous Audit Fixes (Commit 09043e5)

All 15 prior fixes were verified as **genuinely implemented** (not stubs):

| # | Fix | Verified | Evidence |
|---|-----|----------|----------|
| 1 | Gauntlet quality gate | YES | LLM scoring, fails closed at score=35 |
| 2 | RBAC require_permission() | YES | Enforced on run/delete/parallel/agent-run |
| 3 | GDPR deletion cascades | YES | Deletes across campaigns, runs, spend, snapshots, genome |
| 4 | Webhook HMAC verification | YES | SHA-256 HMAC + constant-time comparison |
| 5 | Error normalization | YES | Middleware catches unhandled exceptions |
| 6 | Tool output cap (10KB) | YES | Truncation + sensitive pattern redaction |
| 7 | PII scrubbing fails closed | YES | Blocks LLM on scrub failure |
| 8 | API key rotation | YES | Runtime rotation with format validation |
| 9 | Memory growth bounds | YES | Privacy=1000, replanner=500, sensing=100 |
| 10 | Startup health checks | YES | Supabase, env vars, LLM providers |
| 11 | Whitelabel tenant limits | YES | Max campaigns enforced |
| 12 | Per-provider rate limiting | YES | 60 req/min sliding window |
| 13 | CORS hardening | YES | samesite=strict, 24h cookie |
| 14 | Pagination | YES | limit/offset/total on checkpoints/portfolio |
| 15 | Portfolio batch scoring | YES | Single batch, no N+1 |

---

## Part 2: OWASP Top 10 for Agentic Applications 2026 — Assessment

### ASI-01: Agent Goal Hijack
> Attackers manipulate an agent's overarching objectives via malicious text in tool outputs, memory, or external data.

| Control | Status | Evidence |
|---------|--------|----------|
| Treat external data as untrusted | PARTIAL | Tool outputs are capped/sanitized (10KB, error redaction) but no content-level injection detection on tool results before they enter the ReAct loop |
| Verifiable intent capsules | MISSING | No mechanism to validate that an agent's goal hasn't been modified mid-execution. System prompts are static but tool outputs injected into context are not validated against goal drift |
| Human-in-the-loop for goal changes | PARTIAL | Autonomy levels exist (AUTONOMOUS/GUIDED/HUMAN_OVERRIDE) but there's no runtime detection of goal deviation — only tool-category gating |

**NEW FINDINGS:**
- **Tool outputs are injected directly into agent context without goal-alignment validation** (`engine.py` — tool results go straight into message history)
- **No prompt injection detection** on data returned from web_scrape, crawl_site, research_query, or any other tool that ingests external content

---

### ASI-02: Tool Misuse & Exploitation
> An agent uses an authorized tool in destructive or unintended ways.

| Control | Status | Evidence |
|---------|--------|----------|
| Granular tool permissions | IMPLEMENTED | autonomy.py enforces per-agent tool allowlists/blocklists with category-level gating (SPENDING_TOOLS, OUTBOUND_TOOLS, etc.) |
| Argument validation before execution | PARTIAL | Tool registry executes handlers with timeout but does not validate argument schemas before invocation |
| Rate limiting per tool | MISSING | Rate limiting exists per LLM provider (60/min) but not per tool. An agent could call send_email 1000x in a single run |

**NEW FINDINGS:**
- **No per-tool rate limiting or invocation caps** — only per-provider LLM rate limits exist
- **Tool argument validation is handler-dependent** — registry.execute() passes kwargs directly without schema validation (`tools/registry.py` line ~99)

---

### ASI-03: Identity & Privilege Abuse
> Agents inheriting, escalating, or sharing high-privilege credentials improperly.

| Control | Status | Evidence |
|---------|--------|----------|
| Short-lived task-scoped credentials | MISSING | Agents run with the campaign owner's full permissions for the duration. No JIT credential scoping |
| Agents as managed Non-Human Identities | MISSING | Agents don't have their own identity — they inherit user_id from the request. No agent-level auth tokens |
| Privilege escalation prevention | PARTIAL | RBAC checks happen at route entry but not within the engine loop. A low-privilege user's agent could be served by a route that doesn't check permission |

**NEW FINDINGS:**
- **Campaign clone endpoint missing RBAC** — `routes/campaigns.py` clone uses `get_user_id()` but not `require_permission("campaign", "create")`
- **Dev mode auth bypass** — if `supabase_jwt_secret` is empty, auth middleware allows all localhost access as `dev-user` (`auth.py` lines ~96-101)
- **Tenant user assignment has no authorization** — `whitelabel.py` `add_user_to_tenant()` allows any authenticated user to join any tenant

---

### ASI-04: Agentic Supply Chain Vulnerabilities
> Compromised tools, external MCP servers, or dynamic prompt templates.

| Control | Status | Evidence |
|---------|--------|----------|
| Allowlist MCP connections | N/A | No MCP server integration currently (MCP routes exist but are not wired to external servers) |
| Signed manifests for tools | MISSING | Tool registry accepts any handler registration at startup — no signature verification |
| Dependency pinning | PARTIAL | K8s images use `:latest` tag (`k8s/backend-deployment.yml`, `k8s/webapp-deployment.yml`) — no SHA256 digest pinning |

**NEW FINDINGS:**
- **Container images use `latest` tag with `IfNotPresent`** — mutable tags mean different pods can run different code
- **ECR image scanning enabled but results not enforced** — vulnerable images can be deployed before scan completes

---

### ASI-05: Unexpected Code Execution (RCE)
> Unsafe execution of dynamically generated code.

| Control | Status | Evidence |
|---------|--------|----------|
| Separate generation from execution | IMPLEMENTED | Governance policy evaluation uses safe AST evaluator (`governance.py`) that blocks function calls, imports, attribute access |
| Sandboxed execution | PARTIAL | Code generation tools exist (`fullstack_dev` agent) but tool handlers run in the main process — no VM/sandbox isolation |

**No critical new findings for this category.** The AST-safe evaluator in governance.py is well-implemented.

---

### ASI-06: Memory & Context Poisoning
> Attackers poison RAG databases or long-term agent memory to bias future actions.

| Control | Status | Evidence |
|---------|--------|----------|
| Segment memory per tenant | IMPLEMENTED | Campaign store enforces user_id scoping (`store.py`). Memory is per-campaign |
| Expire unverified data | PARTIAL | Memory growth bounds exist (commit 09043e5 fix #9) but no TTL-based expiry on memory entries |
| Track data provenance | MISSING | Memory entries don't record which agent wrote them or from what source |

**NEW FINDINGS:**
- **Campaign memory shared without locks in parallel runs** — multiple agents call `setattr(memory, k, v)` concurrently on the same CampaignMemory object (`engine.py` parallel execution)
- **No provenance tracking on memory writes** — when an agent writes to campaign memory, there's no record of which agent or tool produced the data
- **Genome marketplace has no integrity verification** — cross-campaign learning data from the genome system is trusted without validation

---

### ASI-07: Insecure Inter-Agent Communication
> Compromised agents sending malicious or spoofed instructions to peer agents.

| Control | Status | Evidence |
|---------|--------|----------|
| mTLS between agents | MISSING | Agent-to-agent comms (`agent_comms.py`) use in-memory message passing with no cryptographic verification |
| Validate message intent | MISSING | Inter-agent messages are plain text strings with no schema validation, signing, or intent verification |
| Zero-trust between agents | MISSING | Agents can send messages to any other agent with no authorization check |

**NEW FINDINGS:**
- **Agent communication has no authentication** — `agent_comms.py` message passing trusts sender identity without verification
- **No message schema validation** — agents can inject arbitrary content into other agents' message queues

---

### ASI-08: Cascading Failures
> A single agent fault propagates widely due to automation and high fan-out.

| Control | Status | Evidence |
|---------|--------|----------|
| Circuit breakers | IMPLEMENTED | `providers.py` has stateful circuit breaker (OPEN/HALF_OPEN/CLOSED) with error thresholds and cooldown |
| Fan-out caps | PARTIAL | Parallel campaign runs exist but no hard cap on concurrent agents. Max iterations per agent capped in engine |
| Tenant isolation | PARTIAL | In-memory state is tenant-scoped but no resource limits per tenant (CPU, memory, concurrent runs) |

**NEW FINDINGS:**
- **No per-tenant concurrency limits** — a single tenant could launch unlimited parallel campaigns, starving others
- **No global agent concurrency cap** — system-wide, there's no limit on total concurrent agent runs

---

### ASI-09: Human-Agent Trust Exploitation
> Agents leverage "authority bias" to manipulate humans into authorizing risky operations.

| Control | Status | Evidence |
|---------|--------|----------|
| Show confidence scores | PARTIAL | Gauntlet quality gate scores content but scores are not exposed to end users in approval UI |
| Independent step-up auth for irreversible actions | PARTIAL | Approval queue exists (`routes/approvals.py`) and gates risky actions, but approval decisions use the same session — no step-up authentication |

**No critical new findings for this category.** Approval queue is genuinely functional.

---

### ASI-10: Rogue Agents
> Agents behave within policies but gradually drift toward unintended actions.

| Control | Status | Evidence |
|---------|--------|----------|
| Baseline agent behavior | PARTIAL | Adaptation module tracks performance snapshots and trends over time (`adaptation.py`). Scoring exists |
| Monitor for objective drift | MISSING | No runtime detection that an agent's outputs are drifting from its configured goals. Gauntlet checks content quality but not goal alignment |
| Automated kill switches | PARTIAL | Engine has max iterations and timeouts but no emergency kill that stops a running agent immediately based on anomaly detection |

**NEW FINDINGS:**
- **No real-time anomaly detection on agent behavior** — scoring happens post-run, not during execution
- **No emergency kill switch API** — once an agent is running, it can only be stopped by timeout or iteration limit, not by an external signal

---

## Part 3: Additional Production Findings (SOC 2 / Infrastructure)

These findings don't map cleanly to the OWASP Agentic Top 10 but are critical for SOC 2 and production readiness:

### Financial Controls (SOC 2: Processing Integrity)

| Finding | Severity | File |
|---------|----------|------|
| TOCTOU race condition: budget check and spend recording are separate async calls with no locking | CRITICAL | `engine.py`, `wallet.py` |
| No asyncio.Lock on wallet, cost tracker, or revshare — concurrent mutations unsafe | CRITICAL | `wallet.py`, `costtracker.py`, `revshare.py` |
| No Stripe idempotency keys — retries create duplicate subscriptions | CRITICAL | `routes/billing.py` |
| Tier/model enforcement is advisory — users can request expensive models on cheap plans | CRITICAL | `engine.py`, `tiers.py` |
| Wallet spend data is purely in-memory — lost on restart | CRITICAL | `wallet.py` |

### Infrastructure Security (SOC 2: Security)

| Finding | Severity | File |
|---------|----------|------|
| Redis exposed on port 6379 with no authentication or network isolation | CRITICAL | `docker-compose.yml` |
| S3 buckets (ALB logs, state) missing public access blocking and encryption | CRITICAL | `terraform/main.tf` |
| Database password in Terraform variables (appears in state file plaintext) | CRITICAL | `terraform/variables.tf` |
| No Kubernetes NetworkPolicies — all pod-to-pod traffic allowed | HIGH | `k8s/` |
| No Pod Security Standards — containers can run as root | HIGH | `k8s/` |
| No WAF on Application Load Balancer | HIGH | `terraform/main.tf` |
| ALB→backend uses HTTP (unencrypted internal traffic) | MEDIUM | `terraform/main.tf` |

### Data Protection (SOC 2: Confidentiality / Privacy)

| Finding | Severity | File |
|---------|----------|------|
| PII scrubbing is opt-in, not auto-applied before LLM calls | HIGH | `privacy.py`, `engine.py` |
| Webhook verification returns `True` when secrets are missing | HIGH | `webhook_auth.py` |
| No CloudTrail audit logging for infrastructure changes | MEDIUM | `terraform/main.tf` |
| Governance violations stored only in memory (not persisted to DB) | MEDIUM | `governance.py` |

---

## Part 4: Summary

### By OWASP Agentic Top 10 Category

| ASI # | Risk | Current State | Critical Gaps |
|-------|------|---------------|---------------|
| ASI-01 | Agent Goal Hijack | PARTIAL | No injection detection on tool outputs |
| ASI-02 | Tool Misuse | PARTIAL | No per-tool rate limiting |
| ASI-03 | Identity & Privilege Abuse | PARTIAL | No agent-level identity, missing RBAC on clone, dev mode bypass |
| ASI-04 | Supply Chain | PARTIAL | Mutable container images, no tool signing |
| ASI-05 | Unexpected Code Execution | GOOD | AST-safe evaluator properly blocks dangerous ops |
| ASI-06 | Memory & Context Poisoning | PARTIAL | Shared memory in parallel, no provenance tracking |
| ASI-07 | Inter-Agent Comms | POOR | No auth, no signing, no schema validation |
| ASI-08 | Cascading Failures | PARTIAL | Circuit breakers exist but no tenant concurrency limits |
| ASI-09 | Human Trust Exploitation | ADEQUATE | Approval queue functional, could add step-up auth |
| ASI-10 | Rogue Agents | PARTIAL | No real-time drift detection or emergency kill switch |

### By Severity

| Severity | Count | Category |
|----------|-------|----------|
| CRITICAL | 8 | Financial controls (5), Infrastructure (3) |
| HIGH | 9 | Auth/RBAC (3), Infrastructure (3), Data protection (2), Agent comms (1) |
| MEDIUM | 5 | Infrastructure (2), Observability (2), Data protection (1) |

### Total: 22 new findings not covered by prior audit

---

## Part 5: Remediation Priority

### Phase 1 — Before Production (blocks deployment)
1. Add `asyncio.Lock` to wallet, cost tracker, revshare (CRITICAL — financial integrity)
2. Enforce tier caps in engine, remove bare `except: pass` (CRITICAL — revenue protection)
3. Persist wallet spend to database (CRITICAL — audit trail)
4. Redis authentication + network isolation (CRITICAL — data exposure)
5. S3 bucket lockdown + secrets management (CRITICAL — data exposure)
6. Authorization on tenant user assignment (CRITICAL — isolation)
7. Stripe idempotency keys (CRITICAL — billing integrity)
8. Combine budget check + spend into atomic operation (CRITICAL — TOCTOU)

### Phase 2 — Before Enterprise Customers (blocks sales)
9. Auto-apply PII scrubbing in LLM pipeline (HIGH — ASI-06, privacy)
10. Agent-level identity and RBAC on all endpoints including clone (HIGH — ASI-03)
11. Fail startup without JWT secret in production (HIGH — ASI-03)
12. Kubernetes hardening: network policies, PSA, image pinning (HIGH — ASI-04)
13. Inter-agent communication auth and schema validation (HIGH — ASI-07)
14. Campaign memory isolation in parallel runs (HIGH — ASI-06)
15. WAF on ALB (HIGH — perimeter defense)

### Phase 3 — First Quarter (operational maturity)
16. Per-tool rate limiting and invocation caps (MEDIUM — ASI-02)
17. Prompt injection detection on tool outputs (MEDIUM — ASI-01)
18. Agent behavior anomaly detection (MEDIUM — ASI-10)
19. Emergency kill switch API (MEDIUM — ASI-10)
20. CloudTrail + governance violation persistence (MEDIUM — observability)
21. Internal TLS (MEDIUM — zero trust)
22. Tenant concurrency limits (MEDIUM — ASI-08)

---

## References

- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP Top 10 for LLM Applications 2025: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
- OWASP LLM Cybersecurity & Governance Checklist v1.1: https://genai.owasp.org/resource/llm-applications-cybersecurity-and-governance-checklist-english/
- NIST AI Risk Management Framework (AI RMF 1.0): https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI Agent Standards Initiative: https://www.pillsburylaw.com/en/news-and-insights/nist-ai-agent-standards.html
- SOC 2 Trust Services Criteria: https://scytale.ai/center/soc-2/the-soc-2-compliance-checklist/
