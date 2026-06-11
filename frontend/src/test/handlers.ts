import { http, HttpResponse } from "msw";
import { candidateUser, sampleResume } from "@/test/fixtures";

/**
 * Default MSW handlers per domain. Tests opt into authenticated state with
 * {@link authedHandlers} or override per-case via `server.use(...)`.
 */
export const authedHandlers = [
  http.get("*/api/v1/users/me", () => HttpResponse.json(candidateUser)),
  http.get("*/api/v1/resumes", () =>
    HttpResponse.json({ items: [sampleResume], total: 1, skip: 0, limit: 20 }),
  ),
  http.get("*/api/v1/analyses", () =>
    HttpResponse.json({ items: [], total: 0, skip: 0, limit: 20 }),
  ),
  http.get("*/api/v1/notifications", () => HttpResponse.json({ items: [], total: 0 })),
];

export const unauthedHandlers = [
  http.get("*/api/v1/users/me", () => new HttpResponse(null, { status: 401 })),
  http.post("*/api/v1/auth/refresh", () => new HttpResponse(null, { status: 401 })),
];
