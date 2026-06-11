import { expect, test } from "@playwright/test";

// Frontend-only smoke journeys — no backend required (served from `vite preview`).
test.describe("smoke", () => {
  test("landing page renders and links to auth", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Log in" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Get started/ }).first()).toBeVisible();
  });

  test("navigates to the login form", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Log in" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("toggles the colour theme", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const wasDark = ((await html.getAttribute("class")) ?? "").includes("dark");
    await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).click();
    const isDark = ((await html.getAttribute("class")) ?? "").includes("dark");
    expect(isDark).not.toBe(wasDark);
  });
});
