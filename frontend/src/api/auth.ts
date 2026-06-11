import { apiClient } from "@/api/client";
import { setAccessToken } from "@/api/token";

export type UserRole = "candidate" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  emailVerified: boolean;
  resumeCount: number;
  analysisCount: number;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  fullName: string;
  password: string;
}

interface MeResponse {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  emailVerified: boolean;
  resumeCount: number;
  analysisCount: number;
}

/** Fetch the current user; resolves to null when not authenticated. */
export async function fetchMe(): Promise<AuthUser | null> {
  try {
    const res = await apiClient.get<MeResponse>("/users/me");
    return res.data;
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "response" in error &&
      (error as { response?: { status?: number } }).response?.status === 401
    ) {
      return null;
    }
    throw error;
  }
}

export async function login(input: LoginInput): Promise<void> {
  const res = await apiClient.post<{ accessToken: string }>("/auth/login", input);
  setAccessToken(res.data.accessToken);
}

export async function register(input: RegisterInput): Promise<void> {
  await apiClient.post("/auth/register", input);
  // Auto-login after a successful registration.
  await login({ email: input.email, password: input.password });
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    setAccessToken(null);
  }
}

export async function forgotPassword(email: string): Promise<void> {
  await apiClient.post("/auth/forgot-password", { email });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/reset-password", { token, newPassword });
}

export interface AuthProviders {
  google: boolean;
  linkedin: boolean;
}

export async function fetchProviders(): Promise<AuthProviders> {
  const res = await apiClient.get<AuthProviders>("/auth/providers");
  return res.data;
}
