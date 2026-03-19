import { AGENTS, DEPARTMENTS, PRICING_TIERS, getAgentsByDepartment } from "@/lib/constants";

describe("AGENTS", () => {
  it("has 27 agents defined", () => {
    expect(AGENTS.length).toBe(27);
  });

  it("each agent has required fields", () => {
    for (const agent of AGENTS) {
      expect(agent.id).toBeTruthy();
      expect(agent.label).toBeTruthy();
      expect(agent.role).toBeTruthy();
      expect(agent.department).toBeTruthy();
      expect(typeof agent.toolCount).toBe("number");
      expect(typeof agent.realTools).toBe("number");
    }
  });

  it("all agent departments match valid department ids", () => {
    const deptIds = DEPARTMENTS.map((d) => d.id);
    for (const agent of AGENTS) {
      expect(deptIds).toContain(agent.department);
    }
  });

  it("has no duplicate agent ids", () => {
    const ids = AGENTS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("DEPARTMENTS", () => {
  it("has 7 departments", () => {
    expect(DEPARTMENTS.length).toBe(7);
  });

  it("each department has required fields", () => {
    for (const dept of DEPARTMENTS) {
      expect(dept.id).toBeTruthy();
      expect(dept.label).toBeTruthy();
      expect(dept.description).toBeTruthy();
      expect(dept.color).toBeTruthy();
    }
  });
});

describe("getAgentsByDepartment", () => {
  it("returns only marketing agents for marketing dept", () => {
    const agents = getAgentsByDepartment("marketing");
    expect(agents.length).toBeGreaterThan(0);
    for (const agent of agents) {
      expect(agent.department).toBe("marketing");
    }
  });

  it("returns empty array for unknown department", () => {
    const agents = getAgentsByDepartment("nonexistent");
    expect(agents).toEqual([]);
  });
});

describe("PRICING_TIERS", () => {
  it("has 3 tiers", () => {
    expect(PRICING_TIERS.length).toBe(3);
  });

  it("growth tier is highlighted", () => {
    const growth = PRICING_TIERS.find((t) => t.id === "growth");
    expect(growth?.highlight).toBe(true);
  });

  it("prices are in ascending order", () => {
    for (let i = 1; i < PRICING_TIERS.length; i++) {
      expect(PRICING_TIERS[i].price).toBeGreaterThan(PRICING_TIERS[i - 1].price);
    }
  });
});
