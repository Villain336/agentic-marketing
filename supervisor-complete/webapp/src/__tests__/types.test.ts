import type {
  AgentStatus, Grade, AgentRun, BusinessProfile, SSEEvent,
  AutonomySettingsResponse, UserSession,
} from "@/types";

describe("Type contracts", () => {
  it("AgentRun satisfies the interface", () => {
    const run: AgentRun = {
      agentId: "prospector",
      status: "running",
      output: "test output",
      grade: "A+",
      score: 95,
      phases: ["Starting...", "Tool: web_search"],
    };
    expect(run.agentId).toBe("prospector");
    expect(run.status).toBe("running");
  });

  it("BusinessProfile satisfies the interface", () => {
    const biz: BusinessProfile = {
      name: "TestCo",
      service: "SaaS Platform",
      icp: "SMB owners",
      geography: "USA",
      goal: "$100k MRR",
      entityType: "llc",
      industry: "Technology",
      founderTitle: "CEO",
      brandContext: "Modern, professional",
    };
    expect(biz.name).toBe("TestCo");
    expect(biz.entityType).toBe("llc");
  });

  it("SSEEvent handles all event types", () => {
    const events: SSEEvent[] = [
      { event: "think", content: "Analyzing..." },
      { event: "tool_call", tool_name: "web_search", tool_input: { query: "test" } },
      { event: "tool_result", tool_output: "results" },
      { event: "output", content: "Final output", memory_update: { key: "val" }, provider: "anthropic" },
      { event: "error", content: "Something failed" },
      { event: "status", content: "running" },
    ];
    expect(events).toHaveLength(6);
  });

  it("AutonomySettingsResponse validates structure", () => {
    const settings: AutonomySettingsResponse = {
      global_level: "guided",
      spending_approval_threshold: 100,
      outbound_approval_required: true,
      content_approval_required: true,
      infrastructure_approval_required: false,
      escalation_channel: "email",
      per_agent: {},
    };
    expect(settings.global_level).toBe("guided");
    expect(settings.spending_approval_threshold).toBe(100);
  });

  it("UserSession has required fields", () => {
    const session: UserSession = {
      accessToken: "tok_123",
      userId: "usr_456",
      email: "test@example.com",
      plan: "growth",
      agencyName: "Test Agency",
    };
    expect(session.accessToken).toBeTruthy();
    expect(session.email).toContain("@");
  });
});
