import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Spinner } from "@/components/ui";
import { useAuth, type UserRole } from "@/lib/auth";

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

/** Redirects unauthenticated users to /login, preserving the target for return. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <FullPageSpinner />;
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

/** Requires a specific role; otherwise renders the 403 page. */
export function RequireRole({ role, children }: { role: UserRole; children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) {
    return <Navigate to="/403" replace />;
  }
  return <>{children}</>;
}

/** Sends already-authenticated users away from public-only pages (login/register). */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (user) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/dashboard"} replace />;
  }
  return <>{children}</>;
}
