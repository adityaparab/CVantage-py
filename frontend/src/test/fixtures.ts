import type { AuthUser } from "@/api/auth";

/** Shared test fixtures (reused by MSW handlers and, later, Playwright). */
export const candidateUser: AuthUser = {
  id: "665c3ef2c9d8f76b6e4f4f01",
  email: "candidate@example.com",
  fullName: "Jane Candidate",
  role: "candidate",
  emailVerified: true,
  resumeCount: 2,
  analysisCount: 3,
};

export const adminUser: AuthUser = {
  id: "665c3ef2c9d8f76b6e4f4f02",
  email: "admin@example.com",
  fullName: "Admin User",
  role: "admin",
  emailVerified: true,
  resumeCount: 0,
  analysisCount: 0,
};

export const sampleResume = {
  id: "665c3ef2c9d8f76b6e4f4f20",
  name: "Backend Engineer Resume",
  source: "created",
  analysisStatus: "completed",
  analysisCount: 1,
  createdAt: "2026-02-01T12:00:00Z",
};
