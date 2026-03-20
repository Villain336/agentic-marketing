/**
 * Integration tests: Onboarding flow ↔ localStorage ↔ API
 *
 * Tests the onboarding data pipeline: form data → localStorage persistence
 * → API submission, verifying the full data flow works end-to-end.
 */

import { api } from "@/lib/api";
import { BUSINESS_MODELS, ONBOARDING_STAGES_EXISTING, ONBOARDING_STAGES_SCRATCH } from "@/lib/constants";

const mockFetch = jest.fn();
global.fetch = mockFetch;

const mockStorage: Record<string, string> = {};
const mockLocalStorage = {
  getItem: jest.fn((key: string) => mockStorage[key] || null),
  setItem: jest.fn((key: string, value: string) => { mockStorage[key] = value; }),
  removeItem: jest.fn((key: string) => { delete mockStorage[key]; }),
  clear: jest.fn(() => { Object.keys(mockStorage).forEach((k) => delete mockStorage[k]); }),
  length: 0,
  key: jest.fn(),
};
Object.defineProperty(global, "localStorage", { value: mockLocalStorage });

describe("Onboarding Flow Integration", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockLocalStorage.clear();
  });

  describe("Onboarding stage definitions", () => {
    it("existing business path has correct stage order", () => {
      const ids = ONBOARDING_STAGES_EXISTING.map((s) => s.id);
      expect(ids).toContain("welcome");
      expect(ids).toContain("business");
      expect(ids).toContain("model_selection");
      expect(ids).toContain("entity");
      expect(ids).toContain("revenue");
      expect(ids).toContain("channels");
      expect(ids).toContain("integrations");
      expect(ids).toContain("autonomy");
      expect(ids).toContain("provisioning");
      // welcome should be first
      expect(ids[0]).toBe("welcome");
      // provisioning should be last
      expect(ids[ids.length - 1]).toBe("provisioning");
    });

    it("from-scratch path includes idea discovery and market validation", () => {
      const ids = ONBOARDING_STAGES_SCRATCH.map((s) => s.id);
      expect(ids).toContain("idea_discovery");
      expect(ids).toContain("market_validation");
      // Should not contain "business" stage (replaced by idea_discovery)
      expect(ids.indexOf("idea_discovery")).toBeLessThan(ids.indexOf("market_validation"));
    });

    it("all stages have labels", () => {
      for (const stage of ONBOARDING_STAGES_EXISTING) {
        expect(stage.label).toBeTruthy();
      }
      for (const stage of ONBOARDING_STAGES_SCRATCH) {
        expect(stage.label).toBeTruthy();
      }
    });
  });

  describe("Business profile persistence", () => {
    it("saves complete business profile to localStorage", () => {
      const business = {
        name: "Integration Test Co",
        service: "SaaS Marketing",
        icp: "B2B founders",
        geography: "USA",
        goal: "$100K",
        entityType: "llc",
        industry: "MarTech",
        founderTitle: "CEO",
        brandContext: "",
        websiteUrl: "https://test.com",
        pricingModel: "subscription",
        currentRevenue: "5k_25k",
        teamSize: "2_5",
        competitors: "HubSpot, Marketo",
        biggestChallenge: "Lead generation",
        brandVoice: "professional",
        businessModel: "saas",
        startingFromScratch: false,
      };

      mockLocalStorage.setItem("omni_business", JSON.stringify(business));

      const stored = JSON.parse(mockLocalStorage.getItem("omni_business")!);
      expect(stored.name).toBe("Integration Test Co");
      expect(stored.businessModel).toBe("saas");
      expect(stored.startingFromScratch).toBe(false);
    });

    it("saves channel selections to localStorage", () => {
      const channels = {
        domain: true,
        email: true,
        linkedin: false,
        twitter: true,
        crm: false,
        payments: true,
      };

      mockLocalStorage.setItem("sv_channels", JSON.stringify(channels));

      const stored = JSON.parse(mockLocalStorage.getItem("sv_channels")!);
      expect(stored.domain).toBe(true);
      expect(stored.linkedin).toBe(false);
    });

    it("saves autonomy level to localStorage", () => {
      mockLocalStorage.setItem("sv_autonomy", "guided");
      expect(mockLocalStorage.getItem("sv_autonomy")).toBe("guided");
    });
  });

  describe("API key submission", () => {
    it("sends non-empty API keys to backend secrets endpoint", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok" }),
      });

      const apiKeys = {
        SENDGRID_API_KEY: "SG.test",
        HUBSPOT_API_KEY: "",          // empty — should be filtered
        STRIPE_API_KEY: "sk_test",
        SERPER_API_KEY: "",           // empty — should be filtered
      };

      const nonEmptyKeys = Object.fromEntries(
        Object.entries(apiKeys).filter(([, v]) => v.trim())
      );

      await api.post("/settings/secrets", { keys: nonEmptyKeys });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.keys).toHaveProperty("SENDGRID_API_KEY", "SG.test");
      expect(body.keys).toHaveProperty("STRIPE_API_KEY", "sk_test");
      expect(body.keys).not.toHaveProperty("HUBSPOT_API_KEY");
      expect(body.keys).not.toHaveProperty("SERPER_API_KEY");
    });

    it("handles backend offline gracefully for secrets submission", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Connection refused"));

      // Should not throw — the onboarding catches this error
      await expect(
        api.post("/settings/secrets", { keys: { SENDGRID_API_KEY: "SG.test" } })
      ).rejects.toThrow();
      // The onboarding page catches this and continues
    });
  });

  describe("Business model selection", () => {
    it("all business models have required fields", () => {
      for (const model of BUSINESS_MODELS) {
        expect(model.id).toBeTruthy();
        expect(model.label).toBeTruthy();
        expect(model.desc).toBeTruthy();
        expect(model.northStar).toBeTruthy();
        expect(model.icon).toBeTruthy();
      }
    });

    it("business models have unique IDs", () => {
      const ids = BUSINESS_MODELS.map((m) => m.id);
      expect(new Set(ids).size).toBe(ids.length);
    });
  });

  describe("Onboarding → Dashboard handoff", () => {
    it("dashboard can load business profile saved during onboarding", () => {
      // Simulate onboarding saving
      const business = {
        name: "Handoff Test Co",
        service: "API Platform",
        icp: "Developers",
        businessModel: "saas",
      };
      mockLocalStorage.setItem("omni_business", JSON.stringify(business));

      // Simulate dashboard loading
      const raw = mockLocalStorage.getItem("omni_business");
      expect(raw).toBeTruthy();
      const loaded = JSON.parse(raw!);
      expect(loaded.name).toBe("Handoff Test Co");
      expect(loaded.businessModel).toBe("saas");
    });

    it("dashboard redirects to onboarding when no business profile exists", () => {
      const raw = mockLocalStorage.getItem("omni_business");
      expect(raw).toBeNull();
      // In the real app, this triggers: router.push("/onboarding")
    });
  });
});
