import { describe, expect, it } from "vitest";
import { captureException, initSentry } from "@/lib/sentry";

describe("sentry (env-gated)", () => {
  it("initSentry is a no-op without VITE_SENTRY_DSN", async () => {
    // No DSN is set in the test env, so the SDK is never imported/initialised.
    await expect(initSentry()).resolves.toBeUndefined();
  });

  it("captureException is a no-op when uninitialised", async () => {
    await expect(captureException(new Error("ignored"))).resolves.toBeUndefined();
  });
});
