import { apiClient } from "@/api/client";
import type { AvailablePlan, TenantSubscription, UpgradeRequestCreate } from "@/types/subscriptionView";

export async function getMySubscription(): Promise<TenantSubscription> {
  const { data } = await apiClient.get<TenantSubscription>("/settings/subscription");
  return data;
}

export async function getAvailablePlans(): Promise<AvailablePlan[]> {
  const { data } = await apiClient.get<AvailablePlan[]>("/settings/subscription/available-plans");
  return data;
}

export async function requestUpgrade(
  payload: UpgradeRequestCreate,
): Promise<TenantSubscription> {
  const { data } = await apiClient.post<TenantSubscription>(
    "/settings/subscription/upgrade-request",
    payload,
  );
  return data;
}
