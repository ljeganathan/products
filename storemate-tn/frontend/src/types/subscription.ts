import type { PlanCode } from "@/types/plan";
import type { SubscriptionStatus } from "@/types/tenant";

export interface Subscription {
  id: string;
  tenant_id: string;
  tenant_name: string;
  plan_id: string;
  plan_code: PlanCode;
  plan_name: string;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  extra_users: number;
  extra_stores: number;
  requested_plan_id: string | null;
  requested_plan_code: PlanCode | null;
  upgrade_requested_at: string | null;
}

export interface SubscriptionCreate {
  tenant_id: string;
  plan_id: string;
}

export interface ChangePlanRequest {
  plan_id: string;
}

export interface SubscriptionUpdate {
  extra_users?: number;
  extra_stores?: number;
}
