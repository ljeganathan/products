import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { Notification } from "@/types/notification";

export interface ListNotificationsParams {
  page?: number;
  page_size?: number;
  store_id?: string;
  is_read?: boolean;
}

export async function listNotifications(
  params: ListNotificationsParams = {},
): Promise<PaginatedResponse<Notification>> {
  const { data } = await apiClient.get<PaginatedResponse<Notification>>("/notifications", {
    params,
  });
  return data;
}

export async function markNotificationRead(id: string): Promise<Notification> {
  const { data } = await apiClient.patch<Notification>(`/notifications/${id}/read`);
  return data;
}
