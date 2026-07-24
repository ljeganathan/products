export type ItemUnit = "pcs" | "kg" | "g" | "l" | "ml" | "box" | "pack";

export interface Item {
  id: string;
  tenant_id: string;
  store_id: string;
  category_id: string;
  name_en: string;
  name_ta: string;
  sku: string | null;
  barcode: string | null;
  unit: ItemUnit;
  mrp_paise: number;
  selling_price_paise: number;
  cost_price_paise: number;
  tax_profile_id: string;
  reorder_level: number;
  reorder_qty: number;
  is_active: boolean;
  brand: string | null;
  pack_size: string | null;
  hsn_code: string | null;
  batch_tracked: boolean;
}

export interface ItemCreate {
  category_id: string;
  store_id?: string | null;
  name_en: string;
  name_ta: string;
  sku?: string | null;
  barcode?: string | null;
  unit: ItemUnit;
  mrp_paise: number;
  selling_price_paise: number;
  cost_price_paise: number;
  tax_profile_id: string;
  reorder_level?: number;
  reorder_qty?: number;
  brand?: string | null;
  pack_size?: string | null;
  hsn_code?: string | null;
  batch_tracked?: boolean;
  opening_stock?: number;
}

export type ItemUpdate = Partial<Omit<ItemCreate, "opening_stock">> & { is_active?: boolean };

export interface BulkImportRowError {
  row_number: number;
  errors: string[];
}

export interface BulkImportResult {
  total_rows: number;
  created_count: number;
  error_count: number;
  errors: BulkImportRowError[];
}

export interface TaxProfile {
  id: string;
  tenant_id: string;
  name: string;
  cgst_pct: number;
  sgst_pct: number;
  igst_pct: number;
  is_default: boolean;
  warning: string | null;
}

export interface TaxProfileCreate {
  name: string;
  cgst_pct?: number;
  sgst_pct?: number;
  igst_pct?: number;
  is_default?: boolean;
}

export type TaxProfileUpdate = Partial<TaxProfileCreate>;
