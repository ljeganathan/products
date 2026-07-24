import { apiClient } from "@/api/client";
import type { Plan, PlanCreate, PlanUpdate } from "@/types/plan";

export async function listPlans(): Promise<Plan[]> {
  const { data } = await apiClient.get<Plan[]>("/platform/plans");
  return data;
}

export async function createPlan(payload: PlanCreate): Promise<Plan> {
  const { data } = await apiClient.post<Plan>("/platform/plans", payload);
  return data;
}

export async function updatePlan(id: string, payload: PlanUpdate): Promise<Plan> {
  const { data } = await apiClient.patch<Plan>(`/platform/plans/${id}`, payload);
  return data;
}
