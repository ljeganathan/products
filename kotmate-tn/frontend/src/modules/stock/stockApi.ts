import { api } from "@/lib/api";

export type StockCalcUnit = "g" | "kg" | "ml" | "l" | "pcs";

export interface StockItem {
  id: string;
  name_en: string;
  name_ta: string | null;
  category_id: string;
  track_inventory: boolean;
  available_qty: number | null;
  // The "Calculate for Me" popup's remembered per-item conversion (e.g. "500 g used
  // per Chicken Biryani") — null until that calculator has been used for this item at
  // least once, in which case the popup pre-fills these instead of asking again.
  stock_calc_qty: number | null;
  stock_calc_unit: StockCalcUnit | null;
}

export async function listStockItems(): Promise<StockItem[]> {
  return (await api.get<StockItem[]>("/api/v1/stock/items")).data;
}

// availableQty: null stops tracking this item entirely (clears track_inventory too) —
// the reverse of giving it a quantity turning tracking on. calc, when given, is only
// ever passed together (both fields) after a "Calculate for Me" add, so the remembered
// conversion is never wiped out by a plain "Type Amount" save.
export async function updateStockItem(
  itemId: string,
  availableQty: number | null,
  calc?: { qty: number; unit: StockCalcUnit },
): Promise<StockItem> {
  return (
    await api.patch<StockItem>(`/api/v1/stock/items/${itemId}`, {
      available_qty: availableQty,
      stock_calc_qty: calc?.qty,
      stock_calc_unit: calc?.unit,
    })
  ).data;
}
