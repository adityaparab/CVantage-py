/**
 * In-memory access-token store (issue #67).
 *
 * The access token is kept in memory only (never localStorage) — the httpOnly
 * refresh cookie persists the session across reloads, and the client bootstraps
 * a fresh access token via the 401 → refresh flow.
 */
let accessToken: string | null = null;
let onAuthFailure: (() => void) | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Registered by the AuthProvider to clear state + redirect on refresh failure. */
export function setAuthFailureHandler(handler: (() => void) | null): void {
  onAuthFailure = handler;
}

export function notifyAuthFailure(): void {
  accessToken = null;
  onAuthFailure?.();
}
