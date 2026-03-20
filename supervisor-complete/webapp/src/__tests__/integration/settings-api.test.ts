/**
 * Integration tests: Settings ↔ API Client
 *
 * Tests the flow of loading settings from the API, modifying them through
 * the UI actions, and saving them back — verifying the full round-trip.
 */

import { api } from "@/lib/api";
import { AGENTS, DEPARTMENTS } from "@/lib/constants";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("Settings ↔ API Integration", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("Autonomy settings round-trip", () => {
    it("loads autonomy settings from backend", async () => {
      const mockSettings = {
        global_level: "guided",
        spending_approval_threshold: 100,
        outbound_approval_required: true,
        content_approval_required: true,
        infrastructure_approval_required: true,
        escalation_channel: "email",
        per_agent: {},
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      });

      const settings = await api.getAutonomySettings();
      expect(settings.global_level).toBe("guided");
      expect(settings.spending_approval_threshold).toBe(100);
      expect(settings.outbound_approval_required).toBe(true);
    });

    it("updates autonomy level", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ global_level: "autonomous" }),
      });

      const result = await api.updateAutonomySettings({ global_level: "autonomous" });
      expect(result.global_level).toBe("autonomous");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/settings/autonomy"),
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ global_level: "autonomous" }),
        })
      );
    });

    it("updates spending threshold", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ spending_approval_threshold: 500 }),
      });

      await api.updateAutonomySettings({ spending_approval_threshold: 500 });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/settings/autonomy"),
        expect.objectContaining({
          body: JSON.stringify({ spending_approval_threshold: 500 }),
        })
      );
    });
  });

  describe("Per-agent settings", () => {
    it("loads agent settings from backend", async () => {
      const mockAgentSettings = {
        prospector: {
          agent_id: "prospector",
          autonomy_level: "autonomous",
          enabled: true,
          max_iterations: 20,
          spending_limit: 50,
          notes: "High priority",
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAgentSettings,
      });

      const settings = await api.getAgentSettings();
      expect(settings["prospector"].autonomy_level).toBe("autonomous");
      expect(settings["prospector"].max_iterations).toBe(20);
    });

    it("updates single agent settings", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agent_id: "prospector", enabled: false }),
      });

      await api.updateAgentSettings("prospector", { enabled: false });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/settings/agents/prospector"),
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ enabled: false }),
        })
      );
    });

    it("batch updates multiple agents", async () => {
      const batch = {
        prospector: { enabled: true, max_iterations: 25 },
        content_writer: { enabled: false },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => batch,
      });

      await api.batchUpdateAgentSettings(batch);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/settings/agents/batch"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(batch),
        })
      );
    });
  });

  describe("Trigger management", () => {
    it("loads triggers list", async () => {
      const mockTriggers = [
        {
          id: "tr_1",
          name: "Low reply rate",
          event_type: "metric_alert",
          source_agent: "sensing",
          action: "rerun_agent",
          target_agent: "outreach_emailer",
          enabled: true,
          cooldown_seconds: 3600,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTriggers,
      });

      const triggers = await api.getTriggers();
      expect(triggers).toHaveLength(1);
      expect(triggers[0].name).toBe("Low reply rate");
      expect(triggers[0].target_agent).toBe("outreach_emailer");
    });

    it("creates a new trigger", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "tr_new" }),
      });

      const result = await api.createTrigger({
        name: "High bounce",
        event_type: "metric_alert",
        action: "rerun_agent",
        target_agent: "content_writer",
        enabled: true,
      });

      expect(result.id).toBe("tr_new");
    });

    it("toggles a trigger enabled/disabled", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "tr_1" }),
      });

      await api.updateTrigger("tr_1", { enabled: false });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/triggers/tr_1"),
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ enabled: false }),
        })
      );
    });

    it("deletes a trigger", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "tr_1" }),
      });

      await api.deleteTrigger("tr_1");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/triggers/tr_1"),
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  describe("Approval queue flow", () => {
    it("loads pending approvals", async () => {
      const mockApprovals = [
        {
          id: "appr_1",
          agent_id: "outreach_emailer",
          action_type: "send_email",
          content: { to: "lead@test.com", subject: "Hello" },
          status: "pending",
          created_at: "2026-03-20T10:00:00Z",
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockApprovals,
      });

      const approvals = await api.getApprovals();
      expect(approvals).toHaveLength(1);
      expect(approvals[0].agent_id).toBe("outreach_emailer");
      expect(approvals[0].action_type).toBe("send_email");
    });

    it("approves a pending item", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "appr_1", status: "approved" }),
      });

      const result = await api.decideApproval("appr_1", "approved");
      expect(result.status).toBe("approved");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/approvals/appr_1/decide"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ decision: "approved" }),
        })
      );
    });

    it("rejects a pending item", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "appr_1", status: "rejected" }),
      });

      const result = await api.decideApproval("appr_1", "rejected");
      expect(result.status).toBe("rejected");
    });
  });

  describe("Events log", () => {
    it("loads events with limit parameter", async () => {
      const mockEvents = Array.from({ length: 5 }, (_, i) => ({
        id: `evt_${i}`,
        type: "agent_completed",
        source_agent: AGENTS[i % AGENTS.length].id,
        campaign_id: "camp_1",
        data: { grade: "A" },
        timestamp: new Date().toISOString(),
      }));

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockEvents,
      });

      const events = await api.getEvents("", 50);
      expect(events).toHaveLength(5);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/events\?.*limit=50/),
        expect.any(Object)
      );
    });

    it("loads event types for trigger creation", async () => {
      const mockTypes = [
        { value: "agent_completed", label: "Agent Completed" },
        { value: "metric_alert", label: "Metric Alert" },
        { value: "approval_needed", label: "Approval Needed" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTypes,
      });

      const types = await api.getEventTypes();
      expect(types).toHaveLength(3);
      expect(types.map((t) => t.value)).toContain("agent_completed");
    });
  });
});
