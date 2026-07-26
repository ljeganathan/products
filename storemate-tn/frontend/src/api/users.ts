import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { User, UserCreate, UserUpdate } from "@/types/user";

export interface ListUsersParams {
  page?: number;
  page_size?: number;
  search?: string;
}

export async function listUsers(params: ListUsersParams = {}): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get<PaginatedResponse<User>>("/users", { params });
  return data;
}

export async function createUser(payload: UserCreate): Promise<User> {
  const { data } = await apiClient.post<User>("/users", payload);
  return data;
}

export async function updateUser(userId: string, payload: UserUpdate): Promise<User> {
  const { data } = await apiClient.patch<User>(`/users/${userId}`, payload);
  return data;
}

export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}
