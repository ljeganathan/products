import { apiClient } from "@/api/client";
import type { GstSummary, SalesReport } from "@/types/report";

export interface ReportRangeParams {
  date_from: string;
  date_to: string;
  store_id?: string;
  cashier_id?: string;
}

export async function getSalesReport(params: ReportRangeParams): Promise<SalesReport> {
  const { data } = await apiClient.get<SalesReport>("/reports/sales", { params });
  return data;
}

export async function getGstSummary(params: ReportRangeParams): Promise<GstSummary> {
  const { data } = await apiClient.get<GstSummary>("/reports/gst-summary", { params });
  return data;
}

export async function downloadSalesCsv(params: ReportRangeParams): Promise<void> {
  const { data } = await apiClient.get<Blob>("/reports/sales.csv", {
    params,
    responseType: "blob",
  });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `sales-${params.date_from}-${params.date_to}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
