import { apiClient } from "@/api/client";

export interface NotificationItem {
  id: string;
  type: "analysis_in_progress" | "analysis_completed" | "analysis_failed";
  analysis_id: string;
  title: string;
  body: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
}

export async function listNotifications(): Promise<NotificationListResponse> {
  const res = await apiClient.get<NotificationListResponse>("/notifications");
  return res.data;
}

export async function clearNotification(id: string): Promise<void> {
  await apiClient.post(`/notifications/${id}/clear`);
}
