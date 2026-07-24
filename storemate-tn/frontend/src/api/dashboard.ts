import { apiClient } from "@/api/client";
import type {
  BreakdownBy,
  BreakdownRow,
  DashboardSummary,
  StoreTotal,
  TrendPoint,
} from "@/types/dashboard";

export interface DateRangeParams {
  date_from: string;
  date_to: string;
  store_id?: string;
}

export async function getDashboardSummary(storeId?: string): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>("/dashboard/summary", {
    params: storeId ? { store_id: storeId } : {},
  });
  return data;
}

export async function getDashboardTrend(
  params: DateRangeParams & { group_by?: "day" | "hour" },
): Promise<TrendPoint[]> {
  const { data } = await apiClient.get<TrendPoint[]>("/dashboard/trend", { params });
  return data;
}

export async function getDashboardBreakdown(
  params: DateRangeParams & { by: BreakdownBy },
): Promise<BreakdownRow[]> {
  const { data } = await apiClient.get<BreakdownRow[]>("/dashboard/breakdown", { params });
  return data;
}

export async function getDashboardStores(
  params: Omit<DateRangeParams, "store_id">,
): Promise<StoreTotal[]> {
  const { data } = await apiClient.get<StoreTotal[]>("/dashboard/stores", { params });
  return data;
}

export async function downloadDashboardPdf(
  params: Omit<DateRangeParams, "store_id">,
): Promise<void> {
  const { data } = await apiClient.get<Blob>("/dashboard/export.pdf", {
    params,
    responseType: "blob",
  });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `dashboard-${params.date_to}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
