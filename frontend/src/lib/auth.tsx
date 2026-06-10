import { createContext, useContext, type ReactNode } from "react";

export type UserRole = "candidate" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
}

export interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

/**
 * Auth context. This is a stub in #66 (always logged-out) so routing/guards can
 * be wired; #67 replaces the provider internals with the real `me` query +
 * login/logout/register mutations. The {@link useAuth} contract stays stable.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const value: AuthState = { user: null, isLoading: false };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
