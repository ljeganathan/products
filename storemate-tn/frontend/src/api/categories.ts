import { apiClient } from "@/api/client";
import type { Category, CategoryCreate, CategoryUpdate } from "@/types/category";
import type { PaginatedResponse } from "@/types/common";

export interface ListCategoriesParams {
  page?: number;
  page_size?: number;
  search?: string;
}

export async function listCategories(
  params: ListCategoriesParams = {},
): Promise<PaginatedResponse<Category>> {
  const { data } = await apiClient.get<PaginatedResponse<Category>>("/categories", { params });
  return data;
}

export async function createCategory(payload: CategoryCreate): Promise<Category> {
  const { data } = await apiClient.post<Category>("/categories", payload);
  return data;
}

export async function updateCategory(id: string, payload: CategoryUpdate): Promise<Category> {
  const { data } = await apiClient.patch<Category>(`/categories/${id}`, payload);
  return data;
}

export async function deleteCategory(id: string): Promise<void> {
  await apiClient.delete(`/categories/${id}`);
}
