import { useCampaignStore, useAuthStore } from "@/lib/store";
import type { AgentRun, Grade } from "@/types";

describe("useCampaignStore", () => {
  beforeEach(() => {
    useCampaignStore.getState().reset();
  });

  it("initializes with default state", () => {
    const state = useCampaignStore.getState();
    expect(state.business).toBeNull();
    expect(state.campaignId).toBe("");
    expect(state.agentRuns).toEqual({});
    expect(state.selectedAgent).toBe("prospector");
    expect(state.selectedDept).toBe("all");
    expect(state.running).toBe(false);
    expect(state.backendStatus).toBe("checking");
  });

  it("sets business profile", () => {
    const biz = {
      name: "TestCo",
      service: "SaaS",
      icp: "SMBs",
      geography: "US",
      goal: "$100k",
      entityType: "llc",
      industry: "Tech",
      founderTitle: "CEO",
      brandContext: "",
    };
    useCampaignStore.getState().setBusiness(biz);
    expect(useCampaignStore.getState().business).toEqual(biz);
  });

  it("updates agent runs", () => {
    const run: Partial<AgentRun> = {
      agentId: "prospector",
      status: "running",
      output: "",
      grade: "—" as Grade,
      score: 0,
      phases: ["Starting..."],
    };
    useCampaignStore.getState().updateAgentRun("prospector", run);
    expect(useCampaignStore.getState().agentRuns["prospector"].status).toBe("running");
  });

  it("merges memory updates", () => {
    useCampaignStore.getState().setMemory({ key1: "val1" });
    useCampaignStore.getState().setMemory({ key2: "val2" });
    const mem = useCampaignStore.getState().memory;
    expect(mem).toEqual({ key1: "val1", key2: "val2" });
  });

  it("sets campaign id", () => {
    useCampaignStore.getState().setCampaignId("camp_123");
    expect(useCampaignStore.getState().campaignId).toBe("camp_123");
  });

  it("sets running state", () => {
    useCampaignStore.getState().setRunning(true);
    expect(useCampaignStore.getState().running).toBe(true);
  });

  it("sets backend status", () => {
    useCampaignStore.getState().setBackendStatus("online");
    expect(useCampaignStore.getState().backendStatus).toBe("online");
  });

  it("sets selected department", () => {
    useCampaignStore.getState().setSelectedDept("marketing");
    expect(useCampaignStore.getState().selectedDept).toBe("marketing");
  });

  it("resets to defaults", () => {
    useCampaignStore.getState().setBusiness({ name: "X" } as any);
    useCampaignStore.getState().setRunning(true);
    useCampaignStore.getState().setCampaignId("camp_123");
    useCampaignStore.getState().reset();
    const state = useCampaignStore.getState();
    expect(state.business).toBeNull();
    expect(state.running).toBe(false);
    expect(state.campaignId).toBe("");
  });
});

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.getState().clearAuth();
  });

  it("initializes with null token and userId", () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.userId).toBeNull();
  });

  it("sets auth credentials", () => {
    useAuthStore.getState().setAuth("tok_123", "user_456");
    const state = useAuthStore.getState();
    expect(state.token).toBe("tok_123");
    expect(state.userId).toBe("user_456");
  });

  it("clears auth credentials", () => {
    useAuthStore.getState().setAuth("tok_123", "user_456");
    useAuthStore.getState().clearAuth();
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.userId).toBeNull();
  });
});
