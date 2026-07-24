import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { Tenant, TenantCreate, TenantUpdate } from "@/types/tenant";

export interface ListTenantsParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
}

export async function listTenants(
  params: ListTenantsParams = {},
): Promise<PaginatedResponse<Tenant>> {
  const { data } = await apiClient.get<PaginatedResponse<Tenant>>("/platform/tenants", { params });
  return data;
}

export async function createTenant(payload: TenantCreate): Promise<Tenant> {
  const { data } = await apiClient.post<Tenant>("/platform/tenants", payload);
  return data;
}

export async function updateTenant(id: string, payload: TenantUpdate): Promise<Tenant> {
  const { data } = await apiClient.patch<Tenant>(`/platform/tenants/${id}`, payload);
  return data;
}
