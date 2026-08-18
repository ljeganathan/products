import { api } from "@/lib/api";

export interface StockItem {
  id: string;
  name_en: string;
  name_ta: string | null;
  category_id: string;
  track_inventory: boolean;
  available_qty: number | null;
}

export async function listStockItems(): Promise<StockItem[]> {
  return (await api.get<StockItem[]>("/api/v1/stock/items")).data;
}

// availableQty: null stops tracking this item entirely (clears track_inventory too) —
// the reverse of giving it a quantity turning tracking on.
export async function updateStockItem(itemId: string, availableQty: number | null): Promise<StockItem> {
  return (await api.patch<StockItem>(`/api/v1/stock/items/${itemId}`, { available_qty: availableQty })).data;
}
