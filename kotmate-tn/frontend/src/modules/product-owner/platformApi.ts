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
  current_period_end: string | null;
}

export interface TenantDetail extends TenantSummary {
  email: string | null;
  phone: string | null;
  door_no: string | null;
  street: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  current_period_start: string | null;
  created_at: string;
}

export interface TenantAdminPasswordReset {
  admin_login_id: string;
  temp_password: string;
}

export interface TenantCreatePayload {
  company_name: string;
  email?: string;
  phone?: string;
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

export interface Invoice {
  id: string;
  tenant_id: string;
  tenant_company_name: string;
  subscription_id: string | null;
  invoice_number: string;
  amount: number;
  status: "draft" | "sent" | "paid" | "overdue";
  issued_date: string;
  due_date: string;
  paid_date: string | null;
  description: string | null;
}

export interface InvoiceCreatePayload {
  tenant_id: string;
  subscription_id?: string;
  amount: number;
  due_date: string;
  description?: string;
}

export interface ExpiringSubscriptionAlert {
  tenant_id: string;
  company_name: string;
  plan_code: string | null;
  current_period_end: string;
  days_remaining: number;
}

export interface OverdueInvoiceAlert {
  invoice_id: string;
  tenant_id: string;
  company_name: string;
  invoice_number: string;
  amount: number;
  due_date: string;
  days_overdue: number;
}

export interface DashboardAlerts {
  expiring_subscriptions: ExpiringSubscriptionAlert[];
  overdue_invoices: OverdueInvoiceAlert[];
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
  payload: Partial<
    Pick<
      TenantDetail,
      | "company_name"
      | "email"
      | "phone"
      | "door_no"
      | "street"
      | "city"
      | "district"
      | "state"
      | "pincode"
      | "is_active"
    >
  >,
): Promise<TenantDetail> {
  return (await api.patch<TenantDetail>(`/api/v1/platform/tenants/${id}`, payload)).data;
}

export async function resetTenantAdminPassword(id: string): Promise<TenantAdminPasswordReset> {
  return (
    await api.post<TenantAdminPasswordReset>(`/api/v1/platform/tenants/${id}/reset-admin-password`)
  ).data;
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

export async function updateSubscriptionPeriod(id: string, currentPeriodEnd: string): Promise<TenantDetail> {
  return (
    await api.patch<TenantDetail>(`/api/v1/platform/tenants/${id}/subscription-period`, {
      current_period_end: currentPeriodEnd,
    })
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

export async function getDashboardAlerts(): Promise<DashboardAlerts> {
  return (await api.get<DashboardAlerts>("/api/v1/platform/dashboard/alerts")).data;
}

export async function listInvoices(params?: {
  tenant_id?: string;
  status?: string;
}): Promise<Invoice[]> {
  return (await api.get<Invoice[]>("/api/v1/platform/invoices", { params })).data;
}

export async function createInvoice(payload: InvoiceCreatePayload): Promise<Invoice> {
  return (await api.post<Invoice>("/api/v1/platform/invoices", payload)).data;
}

export async function markInvoicePaid(id: string): Promise<Invoice> {
  return (await api.patch<Invoice>(`/api/v1/platform/invoices/${id}/mark-paid`)).data;
}

// Invoices have no email-delivery mechanism server-side — this PDF download is the
// actual way to hand an invoice to a tenant. Mirrors reportsApi.ts's downloadReportExport
// (blob response, filename off Content-Disposition, temporary object URL).
export async function downloadInvoicePdf(id: string, fallbackFilename: string): Promise<void> {
  const response = await api.get(`/api/v1/platform/invoices/${id}/pdf`, { responseType: "blob" });
  const disposition = String(response.headers["content-disposition"] ?? "");
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? fallbackFilename;

  const url = window.URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
