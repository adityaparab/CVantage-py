import { apiClient } from "@/api/client";

export interface AdminStats {
  registeredUsers: number;
  totalResumes: number;
  totalAnalyses: number;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await apiClient.get<AdminStats>("/admin/stats");
  return res.data;
}

export interface AdminUser {
  id: string;
  fullName: string;
  email: string;
  role: string;
  status: string;
  registrationDate: string;
  lastActiveAt: string | null;
  resumeCount: number;
  analysisCount: number;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  skip: number;
  limit: number;
}

export async function listAdminUsers(params: {
  search?: string;
  skip?: number;
  limit?: number;
}): Promise<AdminUserList> {
  const res = await apiClient.get<AdminUserList>("/admin/users", { params });
  return res.data;
}

export async function getAdminUser(id: string): Promise<AdminUser> {
  const res = await apiClient.get<AdminUser>(`/admin/users/${id}`);
  return res.data;
}

export async function updateAdminUser(
  id: string,
  patch: { fullName?: string; email?: string },
): Promise<AdminUser> {
  const res = await apiClient.patch<AdminUser>(`/admin/users/${id}`, patch);
  return res.data;
}

export async function resetAdminUserPassword(
  id: string,
  newPassword?: string,
): Promise<{ method: string }> {
  const res = await apiClient.post<{ method: string }>(`/admin/users/${id}/reset-password`, {
    newPassword,
  });
  return res.data;
}

export async function deactivateAdminUser(id: string): Promise<void> {
  await apiClient.post(`/admin/users/${id}/deactivate`);
}

export async function reactivateAdminUser(id: string): Promise<void> {
  await apiClient.post(`/admin/users/${id}/reactivate`);
}

export interface AdminUserResume {
  id: string;
  name: string;
  source: string;
  analysisStatus: string;
  analysisCount: number;
  createdAt: string;
  lastAnalyzedAt: string | null;
}

export async function listAdminUserResumes(userId: string): Promise<{ items: AdminUserResume[] }> {
  const res = await apiClient.get<{ items: AdminUserResume[] }>(`/admin/users/${userId}/resumes`);
  return res.data;
}

export async function deleteAdminResume(resumeId: string): Promise<void> {
  await apiClient.delete(`/admin/resumes/${resumeId}`);
}

export interface AdminModel {
  id: string;
  modelName: string;
  provider: string;
  apiKeyLast4: string;
  usages: string[];
  status: string;
}

export async function listAdminModels(): Promise<{ items: AdminModel[] }> {
  const res = await apiClient.get<{ items: AdminModel[] }>("/admin/models");
  return res.data;
}

export async function createAdminModel(input: {
  modelName: string;
  provider: string;
  apiKey: string;
  usages: string[];
}): Promise<AdminModel> {
  const res = await apiClient.post<AdminModel>("/admin/models", input);
  return res.data;
}

export async function updateAdminModel(
  id: string,
  patch: { status?: string; usages?: string[] },
): Promise<AdminModel> {
  const res = await apiClient.patch<AdminModel>(`/admin/models/${id}`, patch);
  return res.data;
}

export async function rotateAdminModelKey(id: string, apiKey: string): Promise<AdminModel> {
  const res = await apiClient.post<AdminModel>(`/admin/models/${id}/rotate-key`, { apiKey });
  return res.data;
}

export async function deleteAdminModel(id: string): Promise<void> {
  await apiClient.delete(`/admin/models/${id}`);
}
