export interface TopItem {
  name: string;
  revenue_paise: number;
}

export interface DashboardSummary {
  total_paise: number;
  bill_count: number;
  avg_bill_paise: number;
  top_items: TopItem[];
  low_stock_count: number;
}

export interface TrendPoint {
  bucket: string;
  total_paise: number;
  bill_count: number;
}

export type BreakdownBy = "category" | "cashier" | "payment_mode";

export interface BreakdownRow {
  label: string;
  total_paise: number;
  bill_count: number;
}

export interface StoreTotal {
  store_id: string;
  store_name: string;
  total_paise: number;
  bill_count: number;
}
