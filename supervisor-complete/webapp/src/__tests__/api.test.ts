import { api } from "@/lib/api";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ApiClient", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("health()", () => {
    it("returns health data when backend is online", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok", providers: ["anthropic"], agents: 44, tools: 253 }),
      });

      const result = await api.health();
      expect(result.status).toBe("ok");
      expect(result.agents).toBe(44);
    });

    it("returns offline status when fetch fails", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      const result = await api.health();
      expect(result.status).toBe("offline");
      expect(result.agents).toBe(0);
    });
  });

  describe("get()", () => {
    it("makes GET request with correct headers", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: "test" }),
      });

      // Access internal get via a public method
      await api.getCampaigns();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/campaigns"),
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
          credentials: "include",
        })
      );
    });

    it("throws on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(api.getCampaigns()).rejects.toThrow("GET /campaigns: 404");
    });
  });

  describe("post()", () => {
    it("sends POST with JSON body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "camp_1" }),
      });

      const biz = {
        name: "TestCo", service: "SaaS", icp: "SMBs",
        geography: "US", goal: "$100k", entityType: "llc",
        industry: "Tech", founderTitle: "CEO", brandContext: "",
      };

      await api.createCampaign(biz);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/campaign/run"),
        expect.objectContaining({
          method: "POST",
          body: expect.any(String),
        })
      );
    });
  });

  describe("setToken()", () => {
    it("adds Authorization header after setting token", async () => {
      // First call is the session exchange (ignore it)
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      });

      api.setToken("test-token");

      // Now make a request
      await api.health();

      // Find the health call (not the session exchange)
      const healthCall = mockFetch.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/health")
      );
      expect(healthCall).toBeDefined();
      expect(healthCall![1].headers["Authorization"]).toBe("Bearer test-token");

      // Clean up
      api.setToken(null);
    });
  });

  describe("streamAgent()", () => {
    it("returns an AbortController", () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: async () => ({ done: true, value: undefined }),
          }),
        },
      });

      const controller = api.streamAgent(
        "prospector",
        { name: "T", service: "", icp: "", geography: "", goal: "", entityType: "", industry: "", founderTitle: "", brandContext: "" },
        {},
        "camp_1",
        () => {},
        () => {},
        () => {},
      );

      expect(controller).toBeInstanceOf(AbortController);
    });
  });
});
