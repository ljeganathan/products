import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { DiscountRule, DiscountRuleCreate, DiscountRuleUpdate } from "@/types/discountRule";

export interface ListDiscountRulesParams {
  page?: number;
  page_size?: number;
  scope?: string;
  is_active?: boolean;
}

export async function listDiscountRules(
  params: ListDiscountRulesParams = {},
): Promise<PaginatedResponse<DiscountRule>> {
  const { data } = await apiClient.get<PaginatedResponse<DiscountRule>>("/discount-rules", {
    params,
  });
  return data;
}

export async function createDiscountRule(payload: DiscountRuleCreate): Promise<DiscountRule> {
  const { data } = await apiClient.post<DiscountRule>("/discount-rules", payload);
  return data;
}

export async function updateDiscountRule(
  id: string,
  payload: DiscountRuleUpdate,
): Promise<DiscountRule> {
  const { data } = await apiClient.patch<DiscountRule>(`/discount-rules/${id}`, payload);
  return data;
}

export async function deleteDiscountRule(id: string): Promise<void> {
  await apiClient.delete(`/discount-rules/${id}`);
}
