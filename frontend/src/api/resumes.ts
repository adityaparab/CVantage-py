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
    json_resume: { basics: { name } },
  });
  return res.data;
}

export async function saveNewResume(
  name: string,
  jsonResume: Record<string, unknown>,
): Promise<{ id: string }> {
  // The server expects the snake_case `json_resume` key (camelCase aliases apply
  // only to the nested json-resume fields, e.g. startDate).
  const res = await apiClient.post<{ id: string }>("/resumes", { name, json_resume: jsonResume });
  return res.data;
}

export async function deleteResume(id: string): Promise<void> {
  await apiClient.delete(`/resumes/${id}`);
}

export interface ResumeDetail {
  id: string;
  name: string;
  source: string;
  json_resume: Record<string, unknown>;
  analysis_status: string;
  analysis_count: number;
  created_at: string;
  updated_at: string;
}

export async function getResume(id: string): Promise<ResumeDetail> {
  const res = await apiClient.get<ResumeDetail>(`/resumes/${id}`);
  return res.data;
}

export async function updateResume(
  id: string,
  patch: { name?: string; json_resume?: Record<string, unknown> },
): Promise<ResumeDetail> {
  const res = await apiClient.patch<ResumeDetail>(`/resumes/${id}`, patch);
  return res.data;
}
