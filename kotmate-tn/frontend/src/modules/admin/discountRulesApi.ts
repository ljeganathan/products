import { api } from "@/lib/api";

export interface DiscountRule {
  id: string;
  name: string;
  type: "flat_percent" | "item_level" | "coupon";
  discount_mode: "percent" | "rupee";
  value: number | null;
  item_id: string | null;
  item_name_en: string | null;
  coupon_code: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DiscountRuleCreatePayload {
  name: string;
  type: "flat_percent" | "item_level" | "coupon";
  discount_mode: "percent" | "rupee";
  value?: number | null;
  item_id?: string | null;
  coupon_code?: string | null;
  expires_at?: string | null;
}

export interface DiscountRuleUpdatePayload {
  name?: string;
  discount_mode?: "percent" | "rupee";
  value?: number | null;
  item_id?: string | null;
  coupon_code?: string | null;
  expires_at?: string | null;
  is_active?: boolean;
}

export async function listDiscountRules(): Promise<DiscountRule[]> {
  return (await api.get<DiscountRule[]>("/api/v1/discount-rules")).data;
}

export async function createDiscountRule(payload: DiscountRuleCreatePayload): Promise<DiscountRule> {
  return (await api.post<DiscountRule>("/api/v1/discount-rules", payload)).data;
}

export async function updateDiscountRule(
  id: string,
  payload: DiscountRuleUpdatePayload,
): Promise<DiscountRule> {
  return (await api.patch<DiscountRule>(`/api/v1/discount-rules/${id}`, payload)).data;
}
