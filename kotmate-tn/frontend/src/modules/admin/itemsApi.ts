import { api } from "@/lib/api";

export interface Item {
  id: string;
  name_en: string;
  name_ta: string | null;
  category_id: string;
  price: number;
  tax_class_id: string | null;
  item_code: string | null;
  image_url: string | null;
  is_top_seller: boolean;
  is_combo_tile: boolean;
  track_inventory: boolean;
  available_qty: number | null;
  is_active: boolean;
  created_at: string;
}

export interface ItemCreatePayload {
  name_en: string;
  name_ta?: string;
  category_id: string;
  price: number;
  tax_class_id?: string | null;
  item_code?: string | null;
  is_top_seller?: boolean;
  is_combo_tile?: boolean;
  track_inventory?: boolean;
  available_qty?: number | null;
}

export interface ItemUpdatePayload extends Partial<ItemCreatePayload> {
  is_active?: boolean;
}

export interface SectionPriceOption {
  section_id: string;
  section_name_en: string;
  override_price: number | null;
  resolved_price: number;
}

export interface ItemImportResult {
  created: number;
  updated: number;
  errors: string[];
}

export async function listItems(params?: { category_id?: string; search?: string }): Promise<Item[]> {
  return (await api.get<Item[]>("/api/v1/items", { params })).data;
}

export async function createItem(payload: ItemCreatePayload): Promise<Item> {
  return (await api.post<Item>("/api/v1/items", payload)).data;
}

export async function updateItem(id: string, payload: ItemUpdatePayload): Promise<Item> {
  return (await api.patch<Item>(`/api/v1/items/${id}`, payload)).data;
}

export async function restockItem(id: string, availableQty: number): Promise<Item> {
  return (await api.patch<Item>(`/api/v1/items/${id}/restock`, { available_qty: availableQty })).data;
}

export async function uploadItemImage(id: string, file: File): Promise<Item> {
  const form = new FormData();
  form.append("file", file);
  return (
    await api.post<Item>(`/api/v1/items/${id}/image`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  ).data;
}

export async function getSectionPrices(itemId: string): Promise<SectionPriceOption[]> {
  return (await api.get<SectionPriceOption[]>(`/api/v1/items/${itemId}/section-prices`)).data;
}

export async function setSectionPrices(
  itemId: string,
  prices: { section_id: string; price: number | null }[],
): Promise<SectionPriceOption[]> {
  return (
    await api.put<SectionPriceOption[]>(`/api/v1/items/${itemId}/section-prices`, { prices })
  ).data;
}

export async function downloadItemsCsv(): Promise<void> {
  const response = await api.get("/api/v1/items/export.csv", { responseType: "blob" });
  const url = URL.createObjectURL(new Blob([response.data], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "items.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function importItemsCsv(file: File): Promise<ItemImportResult> {
  const form = new FormData();
  form.append("file", file);
  return (
    await api.post<ItemImportResult>("/api/v1/items/import.csv", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  ).data;
}
