import { apiClient } from "@/api/client";

export const JD_MIN = 30;
export const JD_MAX = 50_000;

export type AnalysisStatus = "pending" | "in_progress" | "completed" | "failed" | "cancelled";
export type StepStatus = "pending" | "in_progress" | "completed" | "failed";

export interface AnalysisStep {
  key: string;
  status: StepStatus;
  error: string | null;
}

export interface Suggestion {
  suggestion_id: string;
  group: string;
  field_ref: string;
  title: string;
  description: string;
  proposed_value: string | null;
  applied: boolean;
  dismissed: boolean;
}

export interface InterviewQuestion {
  question: string;
  suggested_answer: string;
}

export interface AnalysisResult {
  overall_score: number;
  ats_score: number;
  project_score: number | null;
  strong_points: string[];
  weak_points: string[];
  matching_skills: string[];
  skill_gaps: string[];
  suggestions: Suggestion[];
  interview_questions: InterviewQuestion[];
}

export interface Analysis {
  id: string;
  name: string;
  resume_id: string;
  job_description: string;
  status: AnalysisStatus;
  steps: AnalysisStep[];
  result: AnalysisResult | null;
  token_usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export async function createAnalysis(input: {
  name: string;
  job_description: string;
  resume_id: string;
}): Promise<Analysis> {
  const res = await apiClient.post<Analysis>("/analyses", input);
  return res.data;
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const res = await apiClient.get<Analysis>(`/analyses/${id}`);
  return res.data;
}

export async function retryAnalysis(id: string): Promise<Analysis> {
  const res = await apiClient.post<Analysis>(`/analyses/${id}/retry`);
  return res.data;
}

export async function applySuggestion(analysisId: string, suggestionId: string): Promise<void> {
  await apiClient.post(`/analyses/${analysisId}/suggestions/${suggestionId}/apply`);
}

export async function dismissSuggestion(analysisId: string, suggestionId: string): Promise<void> {
  await apiClient.post(`/analyses/${analysisId}/suggestions/${suggestionId}/dismiss`);
}
