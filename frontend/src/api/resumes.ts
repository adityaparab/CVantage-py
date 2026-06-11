import { apiClient } from "@/api/client";

export interface ResumeListItem {
  id: string;
  name: string;
  source: string;
  analysis_status: "unanalyzed" | "in_progress" | "completed" | "failed";
  last_analyzed_at: string | null;
  analysis_count: number;
  created_at: string;
}

export interface ResumeListResponse {
  items: ResumeListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface DashboardStats {
  resumeCount: number;
  analysisCount: number;
}

export async function listResumes(params?: { skip?: number; limit?: number }) {
  const res = await apiClient.get<ResumeListResponse>("/resumes", { params });
  return res.data;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await apiClient.get<DashboardStats>("/users/me/stats");
  return res.data;
}

export async function createResume(name: string): Promise<{ id: string }> {
  const res = await apiClient.post<{ id: string }>("/resumes", {
    name,
    jsonResume: { basics: { name } },
  });
  return res.data;
}

export async function saveNewResume(
  name: string,
  jsonResume: Record<string, unknown>,
): Promise<{ id: string }> {
  const res = await apiClient.post<{ id: string }>("/resumes", { name, jsonResume });
  return res.data;
}

export async function deleteResume(id: string): Promise<void> {
  await apiClient.delete(`/resumes/${id}`);
}
