import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/errors";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Never retry auth/permission/validation errors; retry transient ones once.
          if (error instanceof ApiError && [401, 403, 404, 422].includes(error.statusCode)) {
            return false;
          }
          return failureCount < 1;
        },
      },
      mutations: { retry: false },
    },
  });
}
