import { API_URL } from "./constants";
import type {
  SSEEvent, BusinessProfile, Campaign,
  AutonomySettingsResponse, AgentAutonomySettings,
  EventEntry, TriggerRule, ApprovalItemResponse,
} from "@/types";

// ── API Client ──────────────────────────────────────────────────────────

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
    // Exchange token for httpOnly session cookie
    if (token) {
      fetch(`${this.baseUrl}/auth/session`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        credentials: "include",
      }).catch(() => {/* cookie fallback: will use Bearer header */});
    }
  }

  async logout() {
    this.token = null;
    await fetch(`${this.baseUrl}/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, { headers: this.headers(), credentials: "include" });
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
    return res.json();
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
      credentials: "include",
    });
    if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
    return res.json();
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: this.headers(),
      body: JSON.stringify(body),
      credentials: "include",
    });
    if (!res.ok) throw new Error(`PUT ${path}: ${res.status}`);
    return res.json();
  }

  async delete<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.headers(),
      credentials: "include",
    });
    if (!res.ok) throw new Error(`DELETE ${path}: ${res.status}`);
    return res.json();
  }

  async health(): Promise<{ status: string; providers: string[]; agents: number; tools: number }> {
    try {
      return await this.get("/health");
    } catch {
      return { status: "offline", providers: [], agents: 0, tools: 0 };
    }
  }

  // ── Campaign endpoints ──

  async createCampaign(business: BusinessProfile, memory: Record<string, unknown> = {}): Promise<Campaign> {
    return this.post("/campaign/run", { business, memory });
  }

  async getCampaign(id: string): Promise<Campaign> {
    return this.get(`/campaign/${id}`);
  }

  async getCampaigns(): Promise<Campaign[]> {
    return this.get("/campaigns");
  }

  // ── Scoring ──

  async getCampaignScores(campaignId: string): Promise<Record<string, { score: number; grade: string; metrics: Record<string, unknown> }>> {
    return this.get(`/campaign/${campaignId}/scores`);
  }

  // ── Autonomy & Settings ──

  async getAutonomySettings(campaignId: string = ""): Promise<AutonomySettingsResponse> {
    const q = campaignId ? `?campaign_id=${campaignId}` : "";
    return this.get(`/settings/autonomy${q}`);
  }

  async updateAutonomySettings(settings: Partial<AutonomySettingsResponse>, campaignId: string = ""): Promise<AutonomySettingsResponse> {
    const q = campaignId ? `?campaign_id=${campaignId}` : "";
    return this.put(`/settings/autonomy${q}`, settings);
  }

  async getAgentSettings(campaignId: string = ""): Promise<Record<string, AgentAutonomySettings>> {
    const q = campaignId ? `?campaign_id=${campaignId}` : "";
    return this.get(`/settings/agents${q}`);
  }

  async updateAgentSettings(agentId: string, settings: Partial<AgentAutonomySettings>, campaignId: string = ""): Promise<AgentAutonomySettings> {
    const q = campaignId ? `?campaign_id=${campaignId}` : "";
    return this.put(`/settings/agents/${agentId}${q}`, settings);
  }

  async batchUpdateAgentSettings(batch: Record<string, Partial<AgentAutonomySettings>>, campaignId: string = ""): Promise<Record<string, AgentAutonomySettings>> {
    const q = campaignId ? `?campaign_id=${campaignId}` : "";
    return this.post(`/settings/agents/batch${q}`, batch);
  }

  // ── Events & Triggers ──

  async getEvents(campaignId: string = "", limit: number = 50): Promise<EventEntry[]> {
    const params = new URLSearchParams();
    if (campaignId) params.set("campaign_id", campaignId);
    params.set("limit", String(limit));
    return this.get(`/events?${params}`);
  }

  async getTriggers(): Promise<TriggerRule[]> {
    return this.get("/triggers");
  }

  async createTrigger(rule: Partial<TriggerRule>): Promise<{ id: string }> {
    return this.post("/triggers", rule);
  }

  async updateTrigger(ruleId: string, updates: Partial<TriggerRule>): Promise<{ id: string }> {
    return this.put(`/triggers/${ruleId}`, updates);
  }

  async deleteTrigger(ruleId: string): Promise<{ id: string }> {
    return this.delete(`/triggers/${ruleId}`);
  }

  async getEventTypes(): Promise<{ value: string; label: string }[]> {
    return this.get("/triggers/event-types");
  }

  // ── Approvals ──

  async getApprovals(status: string = "pending"): Promise<ApprovalItemResponse[]> {
    return this.get(`/approvals?status=${status}`);
  }

  async decideApproval(itemId: string, decision: "approved" | "rejected"): Promise<{ id: string; status: string }> {
    return this.post(`/approvals/${itemId}/decide`, { decision });
  }

  // ── Agent SSE streaming ──

  streamAgent(
    agentId: string,
    business: BusinessProfile,
    memory: Record<string, unknown>,
    campaignId: string,
    onEvent: (event: SSEEvent) => void,
    onDone: () => void,
    onError: (error: string) => void,
  ): AbortController {
    const controller = new AbortController();

    fetch(`${this.baseUrl}/agent/${agentId}/run`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        agent_id: agentId,
        business,
        memory,
        campaign_id: campaignId,
        tier: "standard",
      }),
      signal: controller.signal,
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          onError(`Agent ${agentId} returned ${res.status}`);
          return;
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
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw || raw === "[DONE]") continue;
            try {
              const evt: SSEEvent = JSON.parse(raw);
              onEvent(evt);
            } catch {
              // skip malformed JSON
            }
          }
        }
        onDone();
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          onError(err.message);
        }
      });

    return controller;
  }
}

export const api = new ApiClient(API_URL);
