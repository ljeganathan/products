import type { DiscountType } from "@/types/bill";

export type DiscountScope = "item" | "category" | "bill";

export interface DiscountRule {
  id: string;
  tenant_id: string;
  scope: DiscountScope;
  target_id: string | null;
  type: DiscountType;
  value: number;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
}

export interface DiscountRuleCreate {
  scope: DiscountScope;
  target_id?: string | null;
  type: DiscountType;
  value: number;
  starts_at?: string | null;
  ends_at?: string | null;
  is_active?: boolean;
}

export interface DiscountRuleUpdate {
  type?: DiscountType;
  value?: number;
  starts_at?: string | null;
  ends_at?: string | null;
  is_active?: boolean;
}
