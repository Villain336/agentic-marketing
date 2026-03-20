/**
 * Integration tests: Dashboard ↔ API Client ↔ Store
 *
 * These tests verify that the API client, Zustand store, and dashboard logic
 * work together correctly — simulating what happens when a user interacts
 * with the dashboard and data flows through the system.
 */

import { api } from "@/lib/api";
import { useCampaignStore } from "@/lib/store";
import { AGENTS } from "@/lib/constants";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("Dashboard ↔ API Integration", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    useCampaignStore.getState().reset();
  });

  describe("Health check → Store update flow", () => {
    it("sets backend status to online when health check succeeds", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok", providers: ["anthropic"], agents: 44, tools: 253 }),
      });

      const health = await api.health();
      const status = health.status === "offline" ? "offline" : "online";
      useCampaignStore.getState().setBackendStatus(status);

      expect(useCampaignStore.getState().backendStatus).toBe("online");
    });

    it("sets backend status to offline when health check fails", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Connection refused"));

      const health = await api.health();
      const status = health.status === "offline" ? "offline" : "online";
      useCampaignStore.getState().setBackendStatus(status);

      expect(useCampaignStore.getState().backendStatus).toBe("offline");
    });
  });

  describe("Campaign creation flow", () => {
    it("creates campaign and stores campaign ID", async () => {
      const mockCampaign = { id: "camp_123", userId: "user1", status: "running" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCampaign,
      });

      const business = {
        name: "Test Co",
        service: "SaaS",
        icp: "SMBs",
        geography: "USA",
        goal: "$100K",
        entityType: "llc",
        industry: "Tech",
        founderTitle: "CEO",
        brandContext: "",
      };

      const campaign = await api.createCampaign(business);
      useCampaignStore.getState().setCampaignId(campaign.id);

      expect(useCampaignStore.getState().campaignId).toBe("camp_123");
    });
  });

  describe("Agent run flow", () => {
    it("updates store through full agent lifecycle: queued → running → done", () => {
      const store = useCampaignStore.getState();
      const agentId = "prospector";

      // Queue agent
      store.updateAgentRun(agentId, {
        agentId,
        status: "queued",
        output: "",
        grade: "—",
        score: 0,
        phases: [],
      });
      expect(useCampaignStore.getState().agentRuns[agentId].status).toBe("queued");

      // Start running
      store.updateAgentRun(agentId, {
        status: "running",
        phases: ["Starting...", "Searching for leads"],
      });
      expect(useCampaignStore.getState().agentRuns[agentId].status).toBe("running");
      expect(useCampaignStore.getState().agentRuns[agentId].phases).toHaveLength(2);

      // Complete with output
      store.updateAgentRun(agentId, {
        status: "done",
        output: "Found 25 qualified leads",
        grade: "A",
        score: 92,
      });
      const run = useCampaignStore.getState().agentRuns[agentId];
      expect(run.status).toBe("done");
      expect(run.output).toBe("Found 25 qualified leads");
      expect(run.grade).toBe("A");
      expect(run.score).toBe(92);
    });

    it("handles agent error status", () => {
      const store = useCampaignStore.getState();
      const agentId = "content_writer";

      store.updateAgentRun(agentId, {
        agentId,
        status: "running",
        output: "",
        grade: "—",
        score: 0,
        phases: ["Starting..."],
      });

      store.updateAgentRun(agentId, {
        status: "error",
        output: "Error: Provider timeout",
      });

      const run = useCampaignStore.getState().agentRuns[agentId];
      expect(run.status).toBe("error");
      expect(run.output).toContain("Provider timeout");
    });
  });

  describe("Score fetching and store sync", () => {
    it("fetches scores from API and updates agent runs with grades", async () => {
      const mockScores = {
        prospector: { score: 92, grade: "A", metrics: { leads_found: 25 } },
        content_writer: { score: 78, grade: "B+", metrics: { posts: 3 } },
        outreach_emailer: { score: 45, grade: "C", metrics: { replies: 2 } },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockScores,
      });

      const scores = await api.getCampaignScores("camp_123");

      // Apply scores to store (as dashboard does)
      const store = useCampaignStore.getState();
      for (const [agentId, scoreData] of Object.entries(scores)) {
        store.updateAgentRun(agentId, {
          grade: scoreData.grade as any,
          score: scoreData.score,
        });
      }

      expect(useCampaignStore.getState().agentRuns["prospector"].grade).toBe("A");
      expect(useCampaignStore.getState().agentRuns["content_writer"].grade).toBe("B+");
      expect(useCampaignStore.getState().agentRuns["outreach_emailer"].score).toBe(45);
    });
  });

  describe("Memory sharing between agents", () => {
    it("accumulates memory updates across multiple agent runs", () => {
      const store = useCampaignStore.getState();

      // Agent 1 produces memory
      store.setMemory({ leads: ["lead1@test.com", "lead2@test.com"] });

      // Agent 2 adds to memory
      store.setMemory({ content_plan: "weekly blog posts" });

      // Agent 3 adds more
      store.setMemory({ outreach_sequence: "3-step cold email" });

      const memory = useCampaignStore.getState().memory;
      expect(memory.leads).toEqual(["lead1@test.com", "lead2@test.com"]);
      expect(memory.content_plan).toBe("weekly blog posts");
      expect(memory.outreach_sequence).toBe("3-step cold email");
    });

    it("later memory updates overwrite earlier ones for the same key", () => {
      const store = useCampaignStore.getState();

      store.setMemory({ strategy: "outbound" });
      store.setMemory({ strategy: "inbound" });

      expect(useCampaignStore.getState().memory.strategy).toBe("inbound");
    });
  });

  describe("Department filtering consistency", () => {
    it("agent constants have valid department assignments", () => {
      const validDepts = new Set(["marketing", "sales", "operations", "finance", "engineering", "intelligence", "legal"]);
      for (const agent of AGENTS) {
        expect(validDepts.has(agent.department)).toBe(true);
      }
    });

    it("store filter integrates with agent constants", () => {
      useCampaignStore.getState().setSelectedDept("marketing");
      const dept = useCampaignStore.getState().selectedDept;
      const filtered = AGENTS.filter((a) => a.department === dept);
      expect(filtered.length).toBeGreaterThan(0);
      expect(filtered.every((a) => a.department === "marketing")).toBe(true);
    });
  });

  describe("Full campaign orchestration flow", () => {
    it("queues all agents then processes them sequentially", () => {
      const store = useCampaignStore.getState();
      const agentOrder = AGENTS.map((a) => a.id);
      const cid = "camp_test_001";
      store.setCampaignId(cid);

      // Queue all
      for (const agentId of agentOrder) {
        store.updateAgentRun(agentId, {
          agentId,
          status: "queued",
          output: "",
          grade: "—",
          score: 0,
          phases: [],
        });
      }

      const runs = useCampaignStore.getState().agentRuns;
      const queuedCount = Object.values(runs).filter((r) => r.status === "queued").length;
      expect(queuedCount).toBe(agentOrder.length);

      // Simulate first agent running
      store.updateAgentRun(agentOrder[0], { status: "running", phases: ["Starting..."] });
      store.setRunning(true);
      store.setSelectedAgent(agentOrder[0]);

      expect(useCampaignStore.getState().running).toBe(true);
      expect(useCampaignStore.getState().selectedAgent).toBe(agentOrder[0]);

      // Complete first agent
      store.updateAgentRun(agentOrder[0], { status: "done", output: "Done", grade: "A" as any });
      store.setRunning(false);

      const doneCount = Object.values(useCampaignStore.getState().agentRuns).filter(
        (r) => r.status === "done"
      ).length;
      expect(doneCount).toBe(1);
    });
  });
});
