import type { PlanCode } from "@/types/plan";
import type { Usage } from "@/types/usage";

export type TenantStatus = "trial" | "active" | "suspended" | "cancelled";
export type SubscriptionStatus = "active" | "past_due" | "cancelled";

export interface Tenant {
  id: string;
  name: string;
  owner_email: string;
  owner_phone: string;
  status: TenantStatus;
  created_at: string;
  subscription_id: string;
  plan_id: string;
  plan_code: PlanCode;
  plan_name: string;
  subscription_status: SubscriptionStatus;
  current_period_end: string;
  usage: Usage;
  has_pending_upgrade_request: boolean;
}

export interface TenantCreate {
  name: string;
  owner_email: string;
  owner_phone: string;
  plan_code: PlanCode;
  store_name?: string | null;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface TenantUpdate {
  status: TenantStatus;
}
