import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { fetchMe, login } from "@/api/auth";
import { getAccessToken, setAccessToken } from "@/api/token";
import { authedHandlers, unauthedHandlers } from "@/test/handlers";
import { server } from "@/test/server";

afterEach(() => setAccessToken(null));

describe("auth API", () => {
  it("fetchMe returns the user when authenticated", async () => {
    server.use(...authedHandlers);
    const user = await fetchMe();
    expect(user?.email).toBe("candidate@example.com");
    expect(user?.role).toBe("candidate");
  });

  it("fetchMe resolves to null when unauthenticated", async () => {
    server.use(...unauthedHandlers);
    expect(await fetchMe()).toBeNull();
  });

  it("login stores the access token", async () => {
    server.use(
      http.post("*/api/v1/auth/login", () => HttpResponse.json({ accessToken: "logged-in" })),
    );
    await login({ email: "a@b.io", password: "x" });
    expect(getAccessToken()).toBe("logged-in");
  });
});
