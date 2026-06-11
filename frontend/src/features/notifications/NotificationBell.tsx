import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearNotification, listNotifications } from "@/api/notifications";
import { queryKeys } from "@/api/queryKeys";
import { cn } from "@/lib/cn";

const TONE: Record<string, string> = {
  analysis_in_progress: "text-warn",
  analysis_completed: "text-success",
  analysis_failed: "text-danger",
};

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: queryKeys.notifications.all,
    queryFn: listNotifications,
    // Poll so in-progress → completed updates appear without SSE.
    refetchInterval: 10_000,
  });
  const items = data?.items ?? [];

  const clearMutation = useMutation({
    mutationFn: clearNotification,
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all }),
  });

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Notifications${items.length ? ` (${items.length} active)` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-[10px] border border-border bg-card text-text hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span aria-hidden="true">🔔</span>
        {items.length > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold text-white">
            {items.length}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded-card border border-border bg-card shadow-lg"
        >
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">No notifications</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {items.map((n) => (
                <li key={n.id} className="border-b border-border last:border-0">
                  <div className="flex items-start justify-between gap-2 px-4 py-3">
                    <button
                      type="button"
                      className="flex-1 text-left focus-visible:outline-2 focus-visible:outline-accent"
                      onClick={() => {
                        setOpen(false);
                        navigate(`/analyses/${n.analysis_id}`);
                      }}
                    >
                      <p className={cn("text-sm font-medium", TONE[n.type] ?? "text-text")}>
                        {n.title}
                      </p>
                      {n.body && <p className="text-xs text-muted">{n.body}</p>}
                    </button>
                    <button
                      type="button"
                      aria-label="Clear notification"
                      onClick={() => clearMutation.mutate(n.id)}
                      className="text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-accent"
                    >
                      ✕
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
