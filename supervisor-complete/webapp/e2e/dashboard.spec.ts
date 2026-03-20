import { test, expect } from "@playwright/test";

// ── Dashboard Tests ──────────────────────────────────────────────────────
// Simulates a user interacting with the main dashboard: viewing agents,
// filtering by department, switching views, and verifying layout elements.

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // Seed localStorage with a business profile so dashboard loads directly
    await page.goto("/");
    await page.evaluate(() => {
      localStorage.setItem(
        "omni_business",
        JSON.stringify({
          name: "E2E Test Co",
          service: "AI Marketing",
          icp: "SaaS founders",
          geography: "USA",
          goal: "$100K",
          entityType: "llc",
          industry: "MarTech",
          founderTitle: "CEO",
          businessModel: "saas",
        })
      );
      localStorage.setItem(
        "omni_session",
        JSON.stringify({
          accessToken: "demo",
          userId: "demo-user",
          email: "test@test.com",
          plan: "growth",
          agencyName: "E2E Agency",
        })
      );
    });
    await page.goto("/dashboard");
  });

  test("renders dashboard with business name in header", async ({ page }) => {
    await expect(page.getByText("E2E Test Co")).toBeVisible();
  });

  test("shows agent sidebar with agent list", async ({ page }) => {
    // Should see some agents in the sidebar
    await expect(page.getByRole("navigation", { name: "Agent list" })).toBeVisible();
    await expect(page.getByRole("listbox", { name: "Agents" })).toBeVisible();
  });

  test("shows department filter badges", async ({ page }) => {
    await expect(page.getByRole("button", { name: "All" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Marketing" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sales" })).toBeVisible();
  });

  test("filters agents by department", async ({ page }) => {
    // Click Marketing department
    await page.getByRole("button", { name: "Marketing" }).click();

    // Should only show marketing agents
    const agentItems = page.getByRole("listbox", { name: "Agents" }).getByRole("option");
    const count = await agentItems.count();
    expect(count).toBeGreaterThan(0);

    // Click All to reset
    await page.getByRole("button", { name: "All" }).click();
    const allCount = await agentItems.count();
    expect(allCount).toBeGreaterThanOrEqual(count);
  });

  test("shows empty state when no agent is running", async ({ page }) => {
    await expect(page.getByText("Select an agent and click")).toBeVisible();
  });

  test("selects an agent from the sidebar", async ({ page }) => {
    // Click on the first agent
    const firstAgent = page.getByRole("listbox", { name: "Agents" }).getByRole("option").first();
    await firstAgent.click();

    // Should show the selected state (brand-50 background)
    await expect(firstAgent).toHaveAttribute("aria-selected", "true");
  });

  test("toggles sidebar visibility", async ({ page }) => {
    // Sidebar should be visible
    const sidebar = page.getByRole("navigation", { name: "Agent list" });
    await expect(sidebar).toBeVisible();

    // Click the collapse button (◀)
    await page.getByRole("button", { name: "◀" }).click();

    // Sidebar should be hidden
    await expect(sidebar).not.toBeVisible();

    // Click expand button (▶)
    await page.getByRole("button", { name: "▶" }).click();
    await expect(sidebar).toBeVisible();
  });

  test("switches between grid and pipeline view", async ({ page }) => {
    // Default is grid view
    await expect(page.getByRole("button", { name: "Grid view" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pipeline view" })).toBeVisible();

    // Switch to pipeline view
    await page.getByRole("button", { name: "Pipeline view" }).click();

    // Pipeline graph SVG should be visible
    await expect(page.locator("svg")).toBeVisible();

    // Switch back to grid
    await page.getByRole("button", { name: "Grid view" }).click();
  });

  test("shows connection status indicator", async ({ page }) => {
    // Should show either Connected or Offline
    const connected = page.getByText("Connected");
    const offline = page.getByText("Offline");
    const isConnected = await connected.isVisible().catch(() => false);
    const isOffline = await offline.isVisible().catch(() => false);
    expect(isConnected || isOffline).toBe(true);
  });

  test("shows agent completion counter", async ({ page }) => {
    // Should show "0/X agents complete" since nothing has run
    await expect(page.getByText(/\d+\/\d+ agents complete/)).toBeVisible();
  });

  test("has Run Full Campaign button", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Run all agents in sequence" })).toBeVisible();
  });

  test("settings button navigates to settings page", async ({ page }) => {
    await page.getByRole("button", { name: "Settings" }).click();
    await page.waitForURL("**/settings", { timeout: 5_000 });
    expect(page.url()).toContain("/settings");
  });

  test("logout clears state and redirects to home", async ({ page }) => {
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForURL("/", { timeout: 5_000 });

    // localStorage should be cleared
    const session = await page.evaluate(() => localStorage.getItem("omni_session"));
    expect(session).toBeNull();
  });

  test("redirects to onboarding if no business profile", async ({ page }) => {
    // Clear business profile and reload
    await page.evaluate(() => localStorage.removeItem("omni_business"));
    await page.goto("/dashboard");
    await page.waitForURL("**/onboarding", { timeout: 5_000 });
    expect(page.url()).toContain("/onboarding");
  });

  test("context panel shows business details on wide screens", async ({ page, viewport }) => {
    // Only visible on xl screens (1280px+)
    if (viewport && viewport.width >= 1280) {
      await expect(page.getByText("Campaign Context")).toBeVisible();
      await expect(page.getByText("E2E Test Co")).toBeVisible();
    }
  });
});
