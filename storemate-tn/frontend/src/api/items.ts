import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { BulkImportResult, Item, ItemCreate, ItemUpdate } from "@/types/item";

export interface ListItemsParams {
  page?: number;
  page_size?: number;
  search?: string;
  category_id?: string;
  store_id?: string;
  barcode?: string;
}

export async function listItems(params: ListItemsParams = {}): Promise<PaginatedResponse<Item>> {
  const { data } = await apiClient.get<PaginatedResponse<Item>>("/items", { params });
  return data;
}

export async function getItem(itemId: string): Promise<Item> {
  const { data } = await apiClient.get<Item>(`/items/${itemId}`);
  return data;
}

export async function createItem(payload: ItemCreate): Promise<Item> {
  const { data } = await apiClient.post<Item>("/items", payload);
  return data;
}

export async function updateItem(itemId: string, payload: ItemUpdate): Promise<Item> {
  const { data } = await apiClient.patch<Item>(`/items/${itemId}`, payload);
  return data;
}

export async function deactivateItem(itemId: string): Promise<void> {
  await apiClient.delete(`/items/${itemId}`);
}

export async function bulkImportItems(file: File, storeId?: string): Promise<BulkImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<BulkImportResult>("/items/bulk-import", formData, {
    params: { store_id: storeId },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function exportItemsCsv(storeId?: string): Promise<void> {
  const { data } = await apiClient.get<Blob>("/items/export.csv", {
    params: { store_id: storeId },
    responseType: "blob",
  });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = "items-export.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function searchPosItems(
  q: string,
  storeId?: string,
  limit = 20,
): Promise<Item[]> {
  const { data } = await apiClient.get<Item[]>("/pos/items/search", {
    params: { q, store_id: storeId, limit },
  });
  return data;
}
