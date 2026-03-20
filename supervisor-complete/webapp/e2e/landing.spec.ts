import { test, expect } from "@playwright/test";

// ── Landing Page Tests ───────────────────────────────────────────────────
// Tests the public landing page: hero, pricing, navigation, and CTAs.

test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders hero section", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("has navigation with login/signup buttons", async ({ page }) => {
    await expect(page.getByRole("link", { name: /log in|sign in/i })).toBeVisible();
  });

  test("shows pricing section with three tiers", async ({ page }) => {
    // Scroll to pricing
    await page.getByText("Pricing").first().click();
    await expect(page.getByText("$497")).toBeVisible();
    await expect(page.getByText("$1,497")).toBeVisible();
    await expect(page.getByText("$4,997")).toBeVisible();
  });

  test("shows agent department tabs", async ({ page }) => {
    // The landing page has department tabs for showcasing agents
    await expect(page.getByText("Marketing").first()).toBeVisible();
    await expect(page.getByText("Sales").first()).toBeVisible();
  });

  test("login link navigates to auth page", async ({ page }) => {
    await page.getByRole("link", { name: /log in|sign in/i }).click();
    await page.waitForURL("**/auth*", { timeout: 5_000 });
    expect(page.url()).toContain("/auth");
  });
});
