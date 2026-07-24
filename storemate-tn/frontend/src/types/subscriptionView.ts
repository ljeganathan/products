import type { PlanCode } from "@/types/plan";
import type { SubscriptionStatus } from "@/types/tenant";
import type { Usage } from "@/types/usage";

export interface TenantSubscription {
  plan_code: PlanCode;
  plan_name: string;
  price_paise: number;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  usage: Usage;
  requested_plan_code: PlanCode | null;
  requested_plan_name: string | null;
  upgrade_requested_at: string | null;
}

export interface UpgradeRequestCreate {
  plan_id: string;
}

export interface AvailablePlan {
  id: string;
  code: PlanCode;
  name: string;
  price_paise: number;
}
