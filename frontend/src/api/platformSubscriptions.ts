import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type {
  ChangePlanRequest,
  Subscription,
  SubscriptionCreate,
  SubscriptionUpdate,
} from "@/types/subscription";

export interface ListSubscriptionsParams {
  page?: number;
  page_size?: number;
  tenant_id?: string;
  status?: string;
}

export async function listSubscriptions(
  params: ListSubscriptionsParams = {},
): Promise<PaginatedResponse<Subscription>> {
  const { data } = await apiClient.get<PaginatedResponse<Subscription>>("/platform/subscriptions", {
    params,
  });
  return data;
}

export async function createSubscription(payload: SubscriptionCreate): Promise<Subscription> {
  const { data } = await apiClient.post<Subscription>("/platform/subscriptions", payload);
  return data;
}

export async function updateSubscription(
  id: string,
  payload: SubscriptionUpdate,
): Promise<Subscription> {
  const { data } = await apiClient.patch<Subscription>(`/platform/subscriptions/${id}`, payload);
  return data;
}

export async function changeSubscriptionPlan(
  id: string,
  payload: ChangePlanRequest,
): Promise<Subscription> {
  const { data } = await apiClient.patch<Subscription>(
    `/platform/subscriptions/${id}/change-plan`,
    payload,
  );
  return data;
}
