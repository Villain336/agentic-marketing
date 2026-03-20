import { test, expect } from "@playwright/test";

// ── Onboarding Flow Tests ────────────────────────────────────────────────
// Simulates a real user going through the full onboarding wizard, filling
// out business info, selecting options, and reaching the dashboard.

test.describe("Onboarding Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Set a demo session so the page doesn't redirect to auth
    await page.goto("/auth");
    await page.getByPlaceholder("you@company.com").fill("test@test.com");
    await page.getByPlaceholder("8+ characters").fill("password123");
    await page.getByRole("button", { name: "Log In" }).click();
    await page.waitForURL("**/onboarding", { timeout: 10_000 });
  });

  test("renders welcome stage with company name input", async ({ page }) => {
    await expect(page.getByText("Let's build your AI team")).toBeVisible();
    await expect(page.getByPlaceholder("Acme Growth Co")).toBeVisible();
  });

  test("shows path selection after entering company name", async ({ page }) => {
    await page.getByPlaceholder("Acme Growth Co").fill("Test Corp");
    await expect(page.getByText("I have an existing business")).toBeVisible();
    await expect(page.getByText("I'm starting from scratch")).toBeVisible();
  });

  test("existing business path shows business details form", async ({ page }) => {
    await page.getByPlaceholder("Acme Growth Co").fill("Test Corp");
    await page.getByText("I have an existing business").click();

    // Should be on business stage
    await expect(page.getByText("Tell us about Test Corp")).toBeVisible();
    await expect(page.getByText("What do you sell?")).toBeVisible();
  });

  test("from scratch path shows idea discovery form", async ({ page }) => {
    await page.getByPlaceholder("Acme Growth Co").fill("New Startup");
    await page.getByText("I'm starting from scratch").click();

    // Should be on idea discovery stage
    await expect(page.getByText("Tell us about your idea")).toBeVisible();
    await expect(page.getByText("What will you sell or offer?")).toBeVisible();
  });

  test("full existing business onboarding flow reaches dashboard", async ({ page }) => {
    // Welcome
    await page.getByPlaceholder("Acme Growth Co").fill("E2E Test Co");
    await page.getByText("I have an existing business").click();

    // Business stage
    await page.locator('input[placeholder="e.g., AI-powered CRM for real estate teams"]').fill("AI Marketing Platform");
    await page.locator('input[placeholder="e.g., Real estate brokerages with 10-50 agents"]').fill("SaaS founders");
    await page.getByRole("button", { name: "Continue" }).click();

    // Model selection stage
    await page.getByText("SaaS").first().click();
    await page.getByRole("button", { name: "Continue" }).click();

    // Entity stage
    await page.getByText("LLC").click();
    await page.getByRole("button", { name: "Continue" }).click();

    // Revenue stage
    await page.getByRole("button", { name: "Continue" }).click();

    // Channels stage
    await page.getByText("Website / Domain").click();
    await page.getByText("Email (SendGrid)").click();
    await page.getByRole("button", { name: "Continue" }).click();

    // Integrations stage — skip, just continue
    await page.getByRole("button", { name: "Continue" }).click();

    // Autonomy stage — select guided (default) and launch
    await page.getByRole("button", { name: "Launch Omni OS" }).click();

    // Provisioning stage shows animation
    await expect(page.getByText("Deploying Agents")).toBeVisible();

    // Wait for redirect to dashboard
    await page.waitForURL("**/dashboard", { timeout: 15_000 });
    expect(page.url()).toContain("/dashboard");
  });

  test("business profile is saved to localStorage after onboarding", async ({ page }) => {
    await page.getByPlaceholder("Acme Growth Co").fill("Storage Test Co");
    await page.getByText("I have an existing business").click();

    await page.locator('input[placeholder="e.g., AI-powered CRM for real estate teams"]').fill("Test Service");
    await page.locator('input[placeholder="e.g., Real estate brokerages with 10-50 agents"]').fill("Test ICP");
    await page.getByRole("button", { name: "Continue" }).click();

    // Model selection
    await page.getByText("SaaS").first().click();
    await page.getByRole("button", { name: "Continue" }).click();

    // Entity
    await page.getByRole("button", { name: "Continue" }).click();

    // Revenue
    await page.getByRole("button", { name: "Continue" }).click();

    // Channels
    await page.getByRole("button", { name: "Continue" }).click();

    // Integrations
    await page.getByRole("button", { name: "Continue" }).click();

    // Autonomy — launch
    await page.getByRole("button", { name: "Launch Omni OS" }).click();

    await page.waitForURL("**/dashboard", { timeout: 15_000 });

    const biz = await page.evaluate(() => localStorage.getItem("omni_business"));
    expect(biz).toBeTruthy();
    const parsed = JSON.parse(biz!);
    expect(parsed.name).toBe("Storage Test Co");
    expect(parsed.service).toBe("Test Service");
  });

  test("progress bar advances through stages", async ({ page }) => {
    // The progress bar width increases as stages progress
    const getProgressWidth = () =>
      page.locator(".h-1 > div").evaluate((el) => el.style.width);

    const initialWidth = await getProgressWidth();

    await page.getByPlaceholder("Acme Growth Co").fill("Progress Co");
    await page.getByText("I have an existing business").click();

    const afterFirstStep = await getProgressWidth();
    // Progress should have increased
    expect(parseFloat(afterFirstStep)).toBeGreaterThan(parseFloat(initialWidth));
  });

  test("back button navigates to previous stage", async ({ page }) => {
    await page.getByPlaceholder("Acme Growth Co").fill("Nav Test Co");
    await page.getByText("I have an existing business").click();

    await expect(page.getByText("Tell us about Nav Test Co")).toBeVisible();

    // Fill required fields and go forward
    await page.locator('input[placeholder="e.g., AI-powered CRM for real estate teams"]').fill("Test");
    await page.locator('input[placeholder="e.g., Real estate brokerages with 10-50 agents"]').fill("Test");
    await page.getByRole("button", { name: "Continue" }).click();

    // Now go back
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByText("Tell us about Nav Test Co")).toBeVisible();
  });
});
