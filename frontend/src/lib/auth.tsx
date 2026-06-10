import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import {
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
  type AuthUser,
  type LoginInput,
  type RegisterInput,
} from "@/api/auth";
import { queryKeys } from "@/api/queryKeys";
import { setAuthFailureHandler } from "@/api/token";

export type { AuthUser, UserRole } from "@/api/auth";

export interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });

  // When a token refresh fails, mark the user logged-out everywhere.
  useEffect(() => {
    setAuthFailureHandler(() => {
      queryClient.setQueryData(queryKeys.auth.me, null);
    });
    return () => setAuthFailureHandler(null);
  }, [queryClient]);

  const refetchMe = () => queryClient.invalidateQueries({ queryKey: queryKeys.auth.me });

  const loginMutation = useMutation({ mutationFn: loginApi, onSuccess: refetchMe });
  const registerMutation = useMutation({ mutationFn: registerApi, onSuccess: refetchMe });
  const logoutMutation = useMutation({
    mutationFn: logoutApi,
    onSuccess: () => queryClient.setQueryData(queryKeys.auth.me, null),
  });

  const value: AuthState = {
    user: data ?? null,
    isLoading,
    login: (input) => loginMutation.mutateAsync(input),
    register: (input) => registerMutation.mutateAsync(input),
    logout: () => logoutMutation.mutateAsync(),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
