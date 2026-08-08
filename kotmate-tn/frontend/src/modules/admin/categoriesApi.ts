import { api } from "@/lib/api";

export interface Category {
  id: string;
  name_en: string;
  name_ta: string | null;
  icon_url: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface CategoryCreatePayload {
  name_en: string;
  name_ta?: string;
  display_order?: number;
}

export interface CategoryUpdatePayload {
  name_en?: string;
  name_ta?: string;
  display_order?: number;
  is_active?: boolean;
}

export async function listCategories(): Promise<Category[]> {
  return (await api.get<Category[]>("/api/v1/categories")).data;
}

export async function createCategory(payload: CategoryCreatePayload): Promise<Category> {
  return (await api.post<Category>("/api/v1/categories", payload)).data;
}

export async function updateCategory(id: string, payload: CategoryUpdatePayload): Promise<Category> {
  return (await api.patch<Category>(`/api/v1/categories/${id}`, payload)).data;
}

export async function uploadCategoryIcon(id: string, file: File): Promise<Category> {
  const form = new FormData();
  form.append("file", file);
  return (
    await api.post<Category>(`/api/v1/categories/${id}/icon`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  ).data;
}

export async function reorderCategories(
  entries: { id: string; display_order: number }[],
): Promise<Category[]> {
  return (await api.put<Category[]>("/api/v1/categories/reorder", { categories: entries })).data;
}
