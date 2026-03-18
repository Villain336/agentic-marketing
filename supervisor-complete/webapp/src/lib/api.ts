import { API_URL } from "./constants";
import type { SSEEvent, BusinessProfile, Campaign } from "@/types";

// ── API Client ──────────────────────────────────────────────────────────

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, { headers: this.headers() });
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
    return res.json();
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
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
