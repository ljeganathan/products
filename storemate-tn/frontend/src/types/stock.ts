export type StockMovementReason = "purchase" | "sale" | "adjustment" | "return" | "damage";

export interface Stock {
  id: string;
  tenant_id: string;
  store_id: string;
  item_id: string;
  item_name_en: string;
  item_name_ta: string;
  barcode: string | null;
  batch_no: string | null;
  expiry_date: string | null;
  quantity_on_hand: number;
  reorder_level: number;
  low_stock: boolean;
  last_restocked_at: string | null;
}

export interface StockMovement {
  id: string;
  tenant_id: string;
  store_id: string;
  item_id: string;
  change_qty: number;
  reason: StockMovementReason;
  reference_id: string | null;
  created_by: string;
  created_at: string;
}

export interface StockAdjustRequest {
  item_id: string;
  store_id?: string | null;
  change_qty: number;
  reason: StockMovementReason;
  reference_id?: string | null;
}
