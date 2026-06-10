import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import { getAccessToken, setAccessToken, setAuthFailureHandler } from "@/api/token";
import { server } from "@/test/server";

beforeEach(() => {
  setAccessToken(null);
});

afterEach(() => {
  setAccessToken(null);
  setAuthFailureHandler(null);
});

describe("apiClient 401 → refresh flow", () => {
  it("refreshes once for concurrent 401s and replays the requests", async () => {
    let refreshCalls = 0;
    server.use(
      http.get("*/api/v1/resumes", ({ request }) => {
        if (request.headers.get("authorization") === "Bearer fresh-token") {
          return HttpResponse.json({ ok: true });
        }
        return new HttpResponse(null, { status: 401 });
      }),
      http.post("*/api/v1/auth/refresh", () => {
        refreshCalls += 1;
        return HttpResponse.json({ accessToken: "fresh-token" });
      }),
    );

    const results = await Promise.all([
      apiClient.get("/resumes"),
      apiClient.get("/resumes"),
      apiClient.get("/resumes"),
    ]);

    expect(refreshCalls).toBe(1);
    expect(results.every((r) => r.status === 200)).toBe(true);
    expect(getAccessToken()).toBe("fresh-token");
  });

  it("logs out (clears token + fires handler) when refresh fails", async () => {
    const onFailure = vi.fn();
    setAuthFailureHandler(onFailure);
    setAccessToken("stale-token");

    server.use(
      http.get("*/api/v1/resumes", () => new HttpResponse(null, { status: 401 })),
      http.post("*/api/v1/auth/refresh", () => new HttpResponse(null, { status: 401 })),
    );

    await expect(apiClient.get("/resumes")).rejects.toBeDefined();
    expect(onFailure).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("does not retry a failing /auth/login (no refresh loop)", async () => {
    let refreshCalls = 0;
    server.use(
      http.post("*/api/v1/auth/login", () => new HttpResponse(null, { status: 401 })),
      http.post("*/api/v1/auth/refresh", () => {
        refreshCalls += 1;
        return HttpResponse.json({ accessToken: "x" });
      }),
    );

    await expect(apiClient.post("/auth/login", {})).rejects.toBeDefined();
    expect(refreshCalls).toBe(0);
  });
});
