import { create } from "zustand";
import type { AgentRun, AgentStatus, BusinessProfile, Department, Grade } from "@/types";

// ── Campaign Store ──────────────────────────────────────────────────────

interface CampaignState {
  business: BusinessProfile | null;
  campaignId: string;
  memory: Record<string, unknown>;
  agentRuns: Record<string, AgentRun>;
  selectedAgent: string;
  selectedDept: Department | "all";
  running: boolean;
  backendStatus: "checking" | "online" | "offline";

  // Actions
  setBusiness: (b: BusinessProfile | null) => void;
  setCampaignId: (id: string) => void;
  setMemory: (update: Record<string, unknown>) => void;
  updateAgentRun: (agentId: string, update: Partial<AgentRun>) => void;
  setSelectedAgent: (id: string) => void;
  setSelectedDept: (dept: Department | "all") => void;
  setRunning: (r: boolean) => void;
  setBackendStatus: (s: "checking" | "online" | "offline") => void;
  reset: () => void;
}

export const useCampaignStore = create<CampaignState>((set) => ({
  business: null,
  campaignId: "",
  memory: {},
  agentRuns: {},
  selectedAgent: "prospector",
  selectedDept: "all",
  running: false,
  backendStatus: "checking",

  setBusiness: (b) => set({ business: b }),
  setCampaignId: (id) => set({ campaignId: id }),
  setMemory: (update) => set((s) => ({ memory: { ...s.memory, ...update } })),
  updateAgentRun: (agentId, update) =>
    set((s) => ({
      agentRuns: {
        ...s.agentRuns,
        [agentId]: { ...s.agentRuns[agentId], ...update } as AgentRun,
      },
    })),
  setSelectedAgent: (id) => set({ selectedAgent: id }),
  setSelectedDept: (dept) => set({ selectedDept: dept }),
  setRunning: (r) => set({ running: r }),
  setBackendStatus: (s) => set({ backendStatus: s }),
  reset: () =>
    set({
      business: null,
      campaignId: "",
      memory: {},
      agentRuns: {},
      selectedAgent: "prospector",
      selectedDept: "all",
      running: false,
      backendStatus: "checking",
    }),
}));


// ── Auth Store ──────────────────────────────────────────────────────────

interface AuthState {
  token: string | null;
  userId: string | null;
  setAuth: (token: string, userId: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  userId: null,
  setAuth: (token, userId) => set({ token, userId }),
  clearAuth: () => set({ token: null, userId: null }),
}));
