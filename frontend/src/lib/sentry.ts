// Env-gated Sentry (issue #95). Zero overhead unless VITE_SENTRY_DSN is set:
// the SDK is dynamically imported, so it never enters the base bundle otherwise.

let ready = false;

export async function initSentry(): Promise<void> {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) return;

  const Sentry = await import("@sentry/react");
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_SENTRY_RELEASE as string | undefined,
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    // Never attach default PII; the app never sends resume/analysis content here.
    sendDefaultPii: false,
  });
  ready = true;
}

export async function captureException(error: unknown): Promise<void> {
  if (!ready) return;
  const Sentry = await import("@sentry/react");
  Sentry.captureException(error);
}
