/** Query-key factory, one namespace per domain (issue #67). */
export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  resumes: {
    all: ["resumes"] as const,
    list: (params?: Record<string, unknown>) => ["resumes", "list", params ?? {}] as const,
    detail: (id: string) => ["resumes", "detail", id] as const,
    stats: ["resumes", "stats"] as const,
  },
  analyses: {
    all: ["analyses"] as const,
    list: (params?: Record<string, unknown>) => ["analyses", "list", params ?? {}] as const,
    detail: (id: string) => ["analyses", "detail", id] as const,
  },
  notifications: {
    all: ["notifications"] as const,
  },
  admin: {
    stats: ["admin", "stats"] as const,
    users: (params?: Record<string, unknown>) => ["admin", "users", params ?? {}] as const,
    models: ["admin", "models"] as const,
  },
} as const;
