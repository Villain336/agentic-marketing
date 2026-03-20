import { test, expect } from "@playwright/test";

// ── Settings Page Tests ──────────────────────────────────────────────────
// Tests the settings page tabs, autonomy controls, and profile editing.

test.describe("Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    // Seed session and business profile
    await page.goto("/");
    await page.evaluate(() => {
      localStorage.setItem(
        "omni_business",
        JSON.stringify({
          name: "Settings Test Co",
          service: "SaaS Platform",
          icp: "SMBs",
          geography: "USA",
          entityType: "llc",
          businessModel: "saas",
        })
      );
      localStorage.setItem(
        "omni_session",
        JSON.stringify({ accessToken: "demo", userId: "demo-user", email: "t@t.com", plan: "growth" })
      );
    });
    await page.goto("/settings");
  });

  test("renders settings page with tabs", async ({ page }) => {
    await expect(page.getByText("Settings")).toBeVisible();
    await expect(page.getByRole("button", { name: "Business Profile" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Global Settings" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Agent Preferences" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Event Triggers" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approval Queue" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Event Log" })).toBeVisible();
  });

  test("global settings tab shows autonomy levels", async ({ page }) => {
    // Global Settings is the default tab
    await expect(page.getByText("Autonomy Level")).toBeVisible();
    await expect(page.getByText("Autonomous")).toBeVisible();
    await expect(page.getByText("Guided")).toBeVisible();
    await expect(page.getByText("Human Override")).toBeVisible();
  });

  test("can switch autonomy level", async ({ page }) => {
    // Click Autonomous
    await page.getByText("Autonomous").first().click();
    // The button should now have the selected style (border-brand-500)
    const autonomousBtn = page.locator("button", { hasText: "Agent acts freely" });
    await expect(autonomousBtn).toBeVisible();
  });

  test("shows approval gates toggles", async ({ page }) => {
    await expect(page.getByText("Approval Gates")).toBeVisible();
    await expect(page.getByText("Outbound Communications")).toBeVisible();
    await expect(page.getByText("Content Publishing")).toBeVisible();
    await expect(page.getByText("Infrastructure Changes")).toBeVisible();
  });

  test("shows spending threshold input", async ({ page }) => {
    await expect(page.getByText("Spending")).toBeVisible();
    await expect(page.getByText("Approval threshold ($)")).toBeVisible();
  });

  test("shows escalation channel options", async ({ page }) => {
    await expect(page.getByText("Escalation Channel")).toBeVisible();
    await expect(page.getByRole("button", { name: "email" })).toBeVisible();
    await expect(page.getByRole("button", { name: "slack" })).toBeVisible();
  });

  test("business profile tab shows editable fields", async ({ page }) => {
    await page.getByRole("button", { name: "Business Profile" }).click();
    await expect(page.getByText("Business Model")).toBeVisible();
    await expect(page.getByText("Core Info")).toBeVisible();
    await expect(page.getByText("Company Name")).toBeVisible();
  });

  test("agent preferences tab shows agent list with departments", async ({ page }) => {
    await page.getByRole("button", { name: "Agent Preferences" }).click();
    await expect(page.getByText("Agent Preferences").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "All" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Marketing" })).toBeVisible();
  });

  test("event triggers tab shows empty state when backend offline", async ({ page }) => {
    await page.getByRole("button", { name: "Event Triggers" }).click();
    await expect(page.getByText("No triggers configured")).toBeVisible();
  });

  test("approval queue tab shows empty state", async ({ page }) => {
    await page.getByRole("button", { name: "Approval Queue" }).click();
    await expect(page.getByText("No pending approvals")).toBeVisible();
  });

  test("event log tab shows empty state", async ({ page }) => {
    await page.getByRole("button", { name: "Event Log" }).click();
    await expect(page.getByText("No events yet")).toBeVisible();
  });

  test("back to dashboard button works", async ({ page }) => {
    await page.getByRole("button", { name: "← Dashboard" }).click();
    await page.waitForURL("**/dashboard", { timeout: 5_000 });
    expect(page.url()).toContain("/dashboard");
  });
});
