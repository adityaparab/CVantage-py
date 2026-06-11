import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config (issue #97).
 *
 * Builds the SPA and serves it with `vite preview`; specs run against that
 * static build. Frontend-only journeys mock the API with `page.route`, so the
 * smoke suite needs no backend. Full-stack specs (tagged @stack) run in CI
 * against the compose stack (#102), where `PLAYWRIGHT_BASE_URL` points at it.
 */
const PORT = 4173;
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
  // When BASE_URL is provided (CI/full-stack), don't spin up the preview server.
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: `pnpm build && pnpm exec vite preview --port ${PORT} --strictPort`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
