import { expect, test } from "@playwright/test";

/**
 * Candidate login → dashboard, with the API mocked via `page.route` so the
 * journey runs without a backend. The full-stack variant (real API + Mongo)
 * runs in CI against the compose stack.
 */
test("candidate logs in and sees their dashboard", async ({ page }) => {
  const me = {
    id: "u1",
    email: "ada@example.com",
    fullName: "Ada Lovelace",
    role: "candidate",
    emailVerified: true,
    resumeCount: 1,
    analysisCount: 0,
  };

  // /me is 401 until login succeeds, so the login route isn't redirected away.
  let loggedIn = false;
  await page.route("**/api/v1/auth/login", (route) => {
    loggedIn = true;
    return route.fulfill({ status: 200, json: { accessToken: "test-token" } });
  });
  await page.route("**/api/v1/users/me", (route) =>
    loggedIn
      ? route.fulfill({ status: 200, json: me })
      : route.fulfill({ status: 401, json: { detail: { message: "Unauthenticated" } } }),
  );
  await page.route("**/api/v1/resumes**", (route) =>
    route.fulfill({
      status: 200,
      json: {
        items: [
          {
            id: "r1",
            name: "Backend Engineer Resume",
            source: "created",
            analysis_status: "unanalyzed",
            analysis_count: 0,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        total: 1,
      },
    }),
  );

  await page.goto("/login");
  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: "Log in" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Backend Engineer Resume")).toBeVisible();
});
