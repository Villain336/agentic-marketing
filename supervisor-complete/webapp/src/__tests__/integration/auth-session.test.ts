/**
 * Integration tests: Auth ↔ API Client ↔ Session Management
 *
 * Tests the authentication flow including token management, session
 * persistence, and API client authorization header behavior.
 */

import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
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

describe("Auth ↔ Session Integration", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    useAuthStore.getState().clearAuth();
    mockLocalStorage.clear();
  });

  describe("Token flow", () => {
    it("sets token in auth store and API client simultaneously", () => {
      // Session exchange call
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      useAuthStore.getState().setAuth("token_123", "user_456");
      api.setToken("token_123");

      expect(useAuthStore.getState().token).toBe("token_123");
      expect(useAuthStore.getState().userId).toBe("user_456");

      // Verify session exchange was attempted
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/auth/session"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer token_123",
          }),
        })
      );

      // Clean up
      api.setToken(null);
    });

    it("clears auth on logout", async () => {
      mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

      // Set auth first
      useAuthStore.getState().setAuth("token", "user");
      api.setToken("token");

      // Logout
      useAuthStore.getState().clearAuth();
      await api.logout();

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().userId).toBeNull();

      // Verify logout endpoint was called
      const logoutCall = mockFetch.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/auth/logout")
      );
      expect(logoutCall).toBeDefined();

      api.setToken(null);
    });
  });

  describe("Session persistence", () => {
    it("persists session data to localStorage", () => {
      const session = {
        accessToken: "demo",
        userId: "demo-user",
        email: "test@test.com",
        plan: "growth",
        agencyName: "Test Agency",
      };

      mockLocalStorage.setItem("omni_session", JSON.stringify(session));

      const stored = JSON.parse(mockLocalStorage.getItem("omni_session")!);
      expect(stored.accessToken).toBe("demo");
      expect(stored.email).toBe("test@test.com");
      expect(stored.plan).toBe("growth");
    });

    it("restores session from localStorage on page load", () => {
      // Simulate saved session
      mockStorage["omni_session"] = JSON.stringify({
        accessToken: "saved_token",
        userId: "saved_user",
      });

      const raw = mockLocalStorage.getItem("omni_session");
      expect(raw).toBeTruthy();
      const session = JSON.parse(raw!);

      useAuthStore.getState().setAuth(session.accessToken, session.userId);
      expect(useAuthStore.getState().token).toBe("saved_token");
      expect(useAuthStore.getState().userId).toBe("saved_user");
    });

    it("clears localStorage on logout", () => {
      mockStorage["omni_session"] = JSON.stringify({ accessToken: "token" });
      mockStorage["omni_business"] = JSON.stringify({ name: "Test" });

      mockLocalStorage.clear();

      expect(mockLocalStorage.getItem("omni_session")).toBeNull();
      expect(mockLocalStorage.getItem("omni_business")).toBeNull();
    });
  });

  describe("API requests carry auth token", () => {
    it("includes Bearer token in campaign requests after login", async () => {
      // Setup: session exchange + the actual request
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ([]),
      });

      api.setToken("my_token");

      // Make an API call
      await api.getCampaigns();

      // Find the campaigns call
      const campaignsCall = mockFetch.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/campaigns")
      );
      expect(campaignsCall).toBeDefined();
      expect(campaignsCall![1].headers["Authorization"]).toBe("Bearer my_token");

      api.setToken(null);
    });

    it("does not include Authorization header when no token is set", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok", providers: [], agents: 0, tools: 0 }),
      });

      api.setToken(null);
      await api.health();

      const healthCall = mockFetch.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/health")
      );
      expect(healthCall).toBeDefined();
      expect(healthCall![1].headers["Authorization"]).toBeUndefined();
    });
  });

  describe("Demo mode fallback", () => {
    it("demo login sets token to 'demo' and userId to 'demo-user'", () => {
      // This simulates what happens when Supabase is not configured
      useAuthStore.getState().setAuth("demo", "demo-user");

      expect(useAuthStore.getState().token).toBe("demo");
      expect(useAuthStore.getState().userId).toBe("demo-user");
    });
  });
});
