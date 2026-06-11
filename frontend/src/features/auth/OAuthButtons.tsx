import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { fetchProviders } from "@/api/auth";

async function startOAuth(provider: "google" | "linkedin") {
  const res = await apiClient.get<{ authorizationUrl: string }>(`/auth/oauth/${provider}/login`);
  window.location.href = res.data.authorizationUrl;
}

/** Renders OAuth buttons only for providers the server reports as enabled (D4). */
export function OAuthButtons() {
  const { data } = useQuery({
    queryKey: ["auth", "providers"],
    queryFn: fetchProviders,
    staleTime: Infinity,
    retry: false,
  });

  if (!data || (!data.google && !data.linkedin)) return null;

  return (
    <div className="mt-4">
      <div className="flex items-center gap-3 py-2 text-xs text-muted">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
      <div className="flex flex-col gap-2">
        {data.google && (
          <button
            type="button"
            onClick={() => startOAuth("google")}
            className="rounded-[10px] border border-border px-4 py-2 text-sm font-medium text-text hover:bg-accent-soft"
          >
            Continue with Google
          </button>
        )}
        {data.linkedin && (
          <button
            type="button"
            onClick={() => startOAuth("linkedin")}
            className="rounded-[10px] border border-border px-4 py-2 text-sm font-medium text-text hover:bg-accent-soft"
          >
            Continue with LinkedIn
          </button>
        )}
      </div>
    </div>
  );
}
