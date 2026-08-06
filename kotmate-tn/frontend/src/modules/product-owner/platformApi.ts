import { api } from "@/lib/api";

export interface TenantSummary {
  id: string;
  tenant_code: string;
  company_name: string;
  is_active: boolean;
  plan_code: string | null;
  subscription_status: string | null;
  billing_cycle: string | null;
  active_user_count: number;
  max_users: number | null;
  active_location_count: number;
  max_locations: number | null;
  admin_login_id: string | null;
}

export interface TenantDetail extends TenantSummary {
  door_no: string | null;
  street: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface TenantCreatePayload {
  company_name: string;
  door_no?: string;
  street?: string;
  city?: string;
  district?: string;
  state: string;
  pincode: string;
  plan_code: string;
  billing_cycle: string;
  location_name: string;
  admin_local_handle: string;
  admin_name: string;
  admin_password: string;
}

export interface Plan {
  id: string;
  code: string;
  name: string;
  max_users: number | null;
  max_locations: number;
  price_monthly: number;
  price_yearly: number;
  features: Record<string, boolean>;
  is_active: boolean;
}

export interface MaintenanceSettings {
  maintenance_mode: boolean;
  maintenance_message: string | null;
  announcement_is_active: boolean;
  announcement_message: string | null;
}

export interface PlatformMetrics {
  active_tenant_count: number;
  mrr_estimate: number;
  total_active_users: number;
  total_max_users: number | null;
  total_active_locations: number;
  total_max_locations: number;
}

export async function listTenants(): Promise<TenantSummary[]> {
  return (await api.get<TenantSummary[]>("/api/v1/platform/tenants")).data;
}

export async function getTenant(id: string): Promise<TenantDetail> {
  return (await api.get<TenantDetail>(`/api/v1/platform/tenants/${id}`)).data;
}

export async function createTenant(payload: TenantCreatePayload): Promise<TenantDetail> {
  return (await api.post<TenantDetail>("/api/v1/platform/tenants", payload)).data;
}

export async function updateTenant(
  id: string,
  payload: Partial<Pick<TenantDetail, "company_name" | "is_active">>,
): Promise<TenantDetail> {
  return (await api.patch<TenantDetail>(`/api/v1/platform/tenants/${id}`, payload)).data;
}

export async function changeTenantPlan(
  id: string,
  planCode: string,
  billingCycle: string,
): Promise<TenantDetail> {
  return (
    await api.post<TenantDetail>(`/api/v1/platform/tenants/${id}/change-plan`, {
      plan_code: planCode,
      billing_cycle: billingCycle,
    })
  ).data;
}

export async function updateSubscriptionStatus(id: string, status: string): Promise<TenantDetail> {
  return (
    await api.patch<TenantDetail>(`/api/v1/platform/tenants/${id}/subscription-status`, { status })
  ).data;
}

export async function listPlans(): Promise<Plan[]> {
  return (await api.get<Plan[]>("/api/v1/platform/plans")).data;
}

export async function updatePlan(id: string, payload: Partial<Plan>): Promise<Plan> {
  return (await api.patch<Plan>(`/api/v1/platform/plans/${id}`, payload)).data;
}

export async function getMaintenanceSettings(): Promise<MaintenanceSettings> {
  return (await api.get<MaintenanceSettings>("/api/v1/platform/maintenance")).data;
}

export async function updateMaintenanceSettings(
  payload: Partial<MaintenanceSettings>,
): Promise<MaintenanceSettings> {
  return (await api.patch<MaintenanceSettings>("/api/v1/platform/maintenance", payload)).data;
}

export async function getPlatformMetrics(): Promise<PlatformMetrics> {
  return (await api.get<PlatformMetrics>("/api/v1/platform/metrics")).data;
}
