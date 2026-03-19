/**
 * @omnios/sdk — Official Omni OS Developer SDK
 *
 * Build agents, integrate via API, manage webhooks, and publish to the marketplace.
 *
 * @example
 * ```ts
 * import { OmniClient } from "@omnios/sdk";
 *
 * const omni = new OmniClient({ apiKey: "omni_xxxxx" });
 *
 * // Run an agent
 * const result = await omni.agents.run("prospector", {
 *   business: { name: "Acme", service: "CRM", icp: "Mid-market SaaS" }
 * });
 *
 * // Stream agent output
 * for await (const event of omni.agents.stream("content", { ... })) {
 *   console.log(event.type, event.data);
 * }
 *
 * // Manage webhooks
 * await omni.webhooks.create({ url: "https://...", events: ["agent.completed"] });
 * ```
 */

// ── Types ──────────────────────────────────────────────────────────────

export interface OmniConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
}

export interface BusinessProfile {
  name: string;
  service: string;
  icp: string;
  geography?: string;
  goal?: string;
  entityType?: string;
  industry?: string;
  businessModel?: string;
  [key: string]: string | boolean | undefined;
}

export interface AgentRunRequest {
  business: BusinessProfile;
  memory?: Record<string, unknown>;
  campaignId?: string;
}

export interface AgentRunResult {
  agentId: string;
  status: "completed" | "error";
  output: string;
  grade?: string;
  score?: number;
  duration?: number;
  provider?: string;
  model?: string;
  memoryUpdate?: Record<string, unknown>;
}

export interface SSEEvent {
  event: "think" | "tool_call" | "tool_result" | "output" | "error" | "status";
  content?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: string;
  memoryUpdate?: Record<string, unknown>;
}

export interface APIKeyInfo {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  rateLimit: number;
  createdAt: string;
  lastUsedAt: string;
  expiresAt: string;
  revoked: boolean;
}

export interface WebhookSubscription {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  secret?: string;
  failureCount: number;
  lastDeliveredAt: string;
}

export interface WebhookDelivery {
  id: string;
  webhookId: string;
  eventType: string;
  payload: Record<string, unknown>;
  statusCode: number;
  success: boolean;
  deliveredAt: string;
}

export interface OAuthApp {
  id: string;
  clientId: string;
  clientSecret?: string;
  name: string;
  redirectUris: string[];
  scopes: string[];
}

export interface AgentManifest {
  name: string;
  version?: string;
  description?: string;
  author?: string;
  category?: string;
  tags?: string[];
  capabilities?: Array<{
    id: string;
    name: string;
    description?: string;
    inputSchema?: Record<string, unknown>;
    outputSchema?: Record<string, unknown>;
  }>;
  endpoint?: string;
  authType?: string;
  streaming?: boolean;
  pricingModel?: string;
  costPerRun?: number;
}

export interface CampaignRunRequest {
  business: BusinessProfile;
  startFrom?: string;
  tier?: "STRONG" | "STANDARD" | "FAST";
}

export interface Campaign {
  id: string;
  status: string;
  agentRuns: Record<string, AgentRunResult>;
  createdAt: string;
}

// ── HTTP Client ────────────────────────────────────────────────────────

class HttpClient {
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;

  constructor(config: OmniConfig) {
    this.baseUrl = (config.baseUrl || "https://api.omnios.dev").replace(/\/$/, "");
    this.apiKey = config.apiKey;
    this.timeout = config.timeout || 30000;
  }

  private headers(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      "X-API-Key": this.apiKey,
      "User-Agent": "OmniOS-SDK/0.1.0",
    };
  }

  async get<T>(path: string): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: this.headers(),
      signal: controller.signal,
    });
    clearTimeout(id);

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new OmniError(res.status, body || res.statusText, path);
    }
    return res.json();
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.headers(),
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    clearTimeout(id);

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new OmniError(res.status, text || res.statusText, path);
    }
    return res.json();
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: this.headers(),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(id);

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new OmniError(res.status, text || res.statusText, path);
    }
    return res.json();
  }

  async delete<T>(path: string): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.headers(),
      signal: controller.signal,
    });
    clearTimeout(id);

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new OmniError(res.status, text || res.statusText, path);
    }
    return res.json();
  }

  async *stream(path: string, body: unknown): AsyncGenerator<SSEEvent> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { ...this.headers(), Accept: "text/event-stream" },
      body: JSON.stringify(body),
    });

    if (!res.ok || !res.body) {
      throw new OmniError(res.status, "Stream failed", path);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data as SSEEvent;
          } catch {
            // skip malformed
          }
        }
      }
    }
  }
}

// ── Error ──────────────────────────────────────────────────────────────

export class OmniError extends Error {
  status: number;
  path: string;

  constructor(status: number, message: string, path: string) {
    super(`Omni API error ${status} on ${path}: ${message}`);
    this.status = status;
    this.path = path;
  }
}

// ── Resource Namespaces ────────────────────────────────────────────────

class Agents {
  constructor(private http: HttpClient) {}

  /** List all available agents. */
  async list(): Promise<{ agents: Array<{ id: string; label: string; role: string }> }> {
    return this.http.get("/agents");
  }

  /** Run a single agent and get the result. */
  async run(agentId: string, req: AgentRunRequest): Promise<AgentRunResult> {
    return this.http.post(`/agent/${agentId}/run`, {
      business: req.business,
      memory: req.memory || {},
      campaign_id: req.campaignId,
    });
  }

  /** Stream agent execution events in real-time. */
  async *stream(agentId: string, req: AgentRunRequest): AsyncGenerator<SSEEvent> {
    yield* this.http.stream(`/agent/${agentId}/run`, {
      business: req.business,
      memory: req.memory || {},
      campaign_id: req.campaignId,
    });
  }
}

class Campaigns {
  constructor(private http: HttpClient) {}

  /** Run a full campaign (all agents in sequence). */
  async run(req: CampaignRunRequest): Promise<Campaign> {
    return this.http.post("/campaign/run", {
      business: req.business,
      start_from: req.startFrom,
      tier: req.tier || "STANDARD",
    });
  }

  /** Get campaign status and results. */
  async get(campaignId: string): Promise<Campaign> {
    return this.http.get(`/campaign/${campaignId}`);
  }

  /** Get campaign scores. */
  async scores(campaignId: string): Promise<Record<string, { score: number; grade: string }>> {
    return this.http.get(`/campaign/${campaignId}/scores`);
  }
}

class Webhooks {
  constructor(private http: HttpClient) {}

  /** Create a webhook subscription. */
  async create(opts: { url: string; events?: string[] }): Promise<WebhookSubscription> {
    return this.http.post("/developer/webhooks", {
      url: opts.url,
      events: opts.events || ["*"],
    });
  }

  /** List all webhook subscriptions. */
  async list(): Promise<{ webhooks: WebhookSubscription[] }> {
    return this.http.get("/developer/webhooks");
  }

  /** Delete a webhook. */
  async delete(webhookId: string): Promise<void> {
    await this.http.delete(`/developer/webhooks/${webhookId}`);
  }

  /** Test a webhook by sending a test event. */
  async test(webhookId: string): Promise<{ delivered: boolean; statusCode: number }> {
    return this.http.post(`/developer/webhooks/${webhookId}/test`, {});
  }

  /** Get recent deliveries for a webhook. */
  async deliveries(webhookId: string, limit?: number): Promise<{ deliveries: WebhookDelivery[] }> {
    return this.http.get(`/developer/webhooks/${webhookId}/deliveries?limit=${limit || 20}`);
  }

  /** List available webhook event types. */
  async events(): Promise<{ events: string[] }> {
    return this.http.get("/developer/webhooks/events");
  }
}

class OAuth {
  constructor(private http: HttpClient) {}

  /** Register an OAuth application. */
  async registerApp(opts: { name: string; redirectUris: string[]; scopes?: string[] }): Promise<OAuthApp> {
    return this.http.post("/developer/oauth/apps", {
      name: opts.name,
      redirect_uris: opts.redirectUris,
      scopes: opts.scopes || ["profile"],
    });
  }

  /** List registered OAuth apps. */
  async listApps(): Promise<{ apps: OAuthApp[] }> {
    return this.http.get("/developer/oauth/apps");
  }

  /** Delete an OAuth app. */
  async deleteApp(appId: string): Promise<void> {
    await this.http.delete(`/developer/oauth/apps/${appId}`);
  }
}

class Protocol {
  constructor(private http: HttpClient) {}

  /** Get the Omni Agent Protocol specification. */
  async spec(): Promise<Record<string, unknown>> {
    return this.http.get("/protocol/spec");
  }

  /** Register an agent with the protocol. */
  async register(manifest: AgentManifest, apiKey?: string): Promise<{ registrationId: string; agentId: string }> {
    return this.http.post("/protocol/agents/register", { manifest, api_key: apiKey });
  }

  /** List registered agents. */
  async list(opts?: { category?: string; listedOnly?: boolean }): Promise<{ agents: AgentManifest[] }> {
    const params = new URLSearchParams();
    if (opts?.category) params.set("category", opts.category);
    if (opts?.listedOnly) params.set("listed_only", "true");
    return this.http.get(`/protocol/agents?${params}`);
  }

  /** Execute a registered external agent. */
  async execute(agentId: string, input: Record<string, unknown>, context?: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.http.post("/protocol/execute", {
      agent_id: agentId,
      input_data: input,
      business_context: context || {},
    });
  }

  /** Submit an agent for marketplace review. */
  async submitForReview(agentId: string): Promise<{ status: string }> {
    return this.http.post(`/protocol/agents/${agentId}/submit-review`, {});
  }
}

// ── Main Client ────────────────────────────────────────────────────────

export class OmniClient {
  private http: HttpClient;

  /** Agents — run, stream, and list agents. */
  agents: Agents;
  /** Campaigns — run full campaigns and get results. */
  campaigns: Campaigns;
  /** Webhooks — subscribe to outbound events. */
  webhooks: Webhooks;
  /** OAuth — register OAuth apps for "Sign in with Omni". */
  oauth: OAuth;
  /** Protocol — register external agents and interact with the Agent Protocol. */
  protocol: Protocol;

  constructor(config: OmniConfig) {
    this.http = new HttpClient(config);
    this.agents = new Agents(this.http);
    this.campaigns = new Campaigns(this.http);
    this.webhooks = new Webhooks(this.http);
    this.oauth = new OAuth(this.http);
    this.protocol = new Protocol(this.http);
  }

  /** Get developer platform info. */
  async info(): Promise<Record<string, unknown>> {
    return this.http.get("/developer/info");
  }

  /** Health check. */
  async health(): Promise<{ status: string }> {
    return this.http.get("/health");
  }
}

export default OmniClient;
