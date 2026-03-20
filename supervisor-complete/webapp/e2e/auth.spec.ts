import { test, expect } from "@playwright/test";

// ── Auth Page Tests ─────────────────────────────────────────────────────
// These tests simulate a real user visiting the auth page, filling forms,
// and completing the login/signup flow (demo mode — no Supabase needed).

test.describe("Auth Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/auth");
  });

  test("renders login form by default", async ({ page }) => {
    await expect(page.getByText("Welcome back")).toBeVisible();
    await expect(page.getByPlaceholder("you@company.com")).toBeVisible();
    await expect(page.getByPlaceholder("8+ characters")).toBeVisible();
    await expect(page.getByRole("button", { name: "Log In" })).toBeVisible();
  });

  test("switches between login and signup tabs", async ({ page }) => {
    // Click Sign Up tab
    await page.getByRole("button", { name: "Sign Up" }).click();
    await expect(page.getByText("Create your account")).toBeVisible();
    await expect(page.getByPlaceholder("Acme Growth Co")).toBeVisible();

    // Click Log In tab
    await page.getByRole("button", { name: "Log In" }).first().click();
    await expect(page.getByText("Welcome back")).toBeVisible();
  });

  test("signup mode shows agency name field", async ({ page }) => {
    await page.goto("/auth?mode=signup");
    await expect(page.getByText("Create your account")).toBeVisible();
    await expect(page.getByText("Agency / Company Name")).toBeVisible();
  });

  test("demo mode login redirects to onboarding", async ({ page }) => {
    // In demo mode (no Supabase env vars), any login goes to /onboarding
    await page.getByPlaceholder("you@company.com").fill("test@example.com");
    await page.getByPlaceholder("8+ characters").fill("password123");
    await page.getByRole("button", { name: "Log In" }).click();

    // Should redirect to onboarding
    await page.waitForURL("**/onboarding", { timeout: 10_000 });
    expect(page.url()).toContain("/onboarding");
  });

  test("demo mode signup redirects to onboarding", async ({ page }) => {
    await page.goto("/auth?mode=signup");
    await page.getByPlaceholder("Acme Growth Co").fill("Test Agency");
    await page.getByPlaceholder("you@company.com").fill("new@example.com");
    await page.getByPlaceholder("8+ characters").fill("password123");
    await page.getByRole("button", { name: "Create Account" }).click();

    await page.waitForURL("**/onboarding", { timeout: 10_000 });
    expect(page.url()).toContain("/onboarding");
  });

  test("persists session to localStorage after login", async ({ page }) => {
    await page.getByPlaceholder("you@company.com").fill("test@example.com");
    await page.getByPlaceholder("8+ characters").fill("password123");
    await page.getByRole("button", { name: "Log In" }).click();

    await page.waitForURL("**/onboarding", { timeout: 10_000 });

    const session = await page.evaluate(() => localStorage.getItem("omni_session"));
    expect(session).toBeTruthy();
    const parsed = JSON.parse(session!);
    expect(parsed).toHaveProperty("accessToken");
    expect(parsed).toHaveProperty("userId");
  });

  test("shows terms of service footer", async ({ page }) => {
    await expect(page.getByText("Terms of Service")).toBeVisible();
  });
});
