import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { PlatformUserUpdate, User } from "@/types/user";

export async function listTenantUsers(tenantId: string): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get<PaginatedResponse<User>>(
    `/platform/tenants/${tenantId}/users`,
    { params: { page_size: 50 } },
  );
  return data;
}

export async function updateTenantUser(
  tenantId: string,
  userId: string,
  payload: PlatformUserUpdate,
): Promise<User> {
  const { data } = await apiClient.patch<User>(
    `/platform/tenants/${tenantId}/users/${userId}`,
    payload,
  );
  return data;
}
