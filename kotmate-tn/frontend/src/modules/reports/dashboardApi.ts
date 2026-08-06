import { api } from "@/lib/api";

export interface TopItemRow {
  item_id: string;
  name_en: string;
  quantity_sold: number;
}

export interface HourlySalesPoint {
  hour: number;
  sales: number;
}

export interface DashboardSummary {
  report_date: string;
  today_sales: number;
  bill_count: number;
  average_bill_value: number;
  top_items: TopItemRow[];
  hourly_trend: HourlySalesPoint[];
}

export interface LocationComparisonRow {
  location_id: string;
  location_name: string;
  sales: number;
  bill_count: number;
}

export interface MultiLocationComparison {
  rows: LocationComparisonRow[];
}

export async function getDashboardSummary(params?: {
  report_date?: string;
  location_id?: string;
}): Promise<DashboardSummary> {
  return (await api.get<DashboardSummary>("/api/v1/dashboard/summary", { params })).data;
}

export async function getMultiLocationComparison(params: {
  date_from: string;
  date_to: string;
}): Promise<MultiLocationComparison> {
  return (await api.get<MultiLocationComparison>("/api/v1/dashboard/multi-location", { params })).data;
}
