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

export interface LowStockItemRow {
  item_id: string;
  name_en: string;
  name_ta: string | null;
  available_qty: number;
}

export interface LowStockItemsResponse {
  rows: LowStockItemRow[];
}

export async function getLowStockItems(): Promise<LowStockItemsResponse> {
  return (await api.get<LowStockItemsResponse>("/api/v1/dashboard/low-stock-items")).data;
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

export interface HourlyItemRow {
  item_id: string;
  name_en: string;
  sales: number;
  quantity_sold: number;
}

export interface HourlyItemBreakdown {
  hour: number;
  rows: HourlyItemRow[];
}

export async function getHourlyItemBreakdown(params: {
  hour: number;
  report_date?: string;
  location_id?: string;
}): Promise<HourlyItemBreakdown> {
  return (await api.get<HourlyItemBreakdown>("/api/v1/dashboard/hourly-items", { params })).data;
}

export async function getMultiLocationComparison(params: {
  date_from: string;
  date_to: string;
}): Promise<MultiLocationComparison> {
  return (await api.get<MultiLocationComparison>("/api/v1/dashboard/multi-location", { params })).data;
}

export interface SalesTrendPoint {
  label: string;
  sales: number;
}

export interface SalesTrend {
  period: "monthly" | "yearly";
  points: SalesTrendPoint[];
}

export async function getSalesTrend(params: {
  period: "monthly" | "yearly";
  location_id?: string;
}): Promise<SalesTrend> {
  return (await api.get<SalesTrend>("/api/v1/dashboard/sales-trend", { params })).data;
}
