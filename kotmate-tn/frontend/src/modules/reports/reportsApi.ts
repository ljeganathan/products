import { api } from "@/lib/api";

export interface ReportFilterParams {
  date_from: string;
  date_to: string;
  location_id?: string;
  // Lets a `ReportFilterParams` value be passed anywhere a plain query-params record
  // is expected (e.g. `getReport`'s shared helper) without a separate cast.
  [key: string]: string | undefined;
}

export type ExportFormat = "csv" | "excel" | "pdf";

export interface SalesSummary {
  bill_count: number;
  subtotal: number;
  discount_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  round_off_amount: number;
  grand_total: number;
  average_bill_value: number;
}

export interface ItemWiseSalesRow {
  item_id: string;
  name_en: string;
  name_ta: string | null;
  quantity_sold: number;
  revenue: number;
}
export interface ItemWiseSales {
  rows: ItemWiseSalesRow[];
  total_revenue: number;
}

export interface CategoryWiseSalesRow {
  category_id: string;
  name_en: string;
  name_ta: string | null;
  quantity_sold: number;
  revenue: number;
}
export interface CategoryWiseSales {
  rows: CategoryWiseSalesRow[];
  total_revenue: number;
}

export interface TaxSummary {
  taxable_value: number;
  cgst_amount: number;
  sgst_amount: number;
  total_tax: number;
}

export interface WaiterSalesRow {
  waiter_id: string;
  waiter_name: string;
  bill_count: number;
  net_sale_value: number;
}
export interface WaiterSales {
  rows: WaiterSalesRow[];
  total_net_sale_value: number;
}

export interface CashierSalesRow {
  pos_user_id: string;
  login_id: string;
  name: string;
  bill_count: number;
  net_sale_value: number;
}
export interface CashierSales {
  rows: CashierSalesRow[];
  total_net_sale_value: number;
}

export interface WaiterIncentiveRow {
  waiter_id: string;
  waiter_name: string;
  net_sale_value: number;
  incentive_amount: number;
}
export interface WaiterIncentive {
  rows: WaiterIncentiveRow[];
  total_incentive_amount: number;
}

export interface CashierIncentiveRow {
  pos_user_id: string;
  login_id: string;
  name: string;
  net_sale_value: number;
  incentive_amount: number;
}
export interface CashierIncentive {
  rows: CashierIncentiveRow[];
  total_incentive_amount: number;
}

export interface PaymentMethodTotal {
  method: string;
  amount: number;
}
export interface ZReport {
  report_date: string;
  bill_count: number;
  subtotal: number;
  discount_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  round_off_amount: number;
  grand_total: number;
  payments: PaymentMethodTotal[];
}

async function getReport<T>(path: string, params: Record<string, string | undefined>): Promise<T> {
  return (await api.get<T>(`/api/v1/reports/${path}`, { params })).data;
}

export const getSalesSummary = (params: ReportFilterParams) => getReport<SalesSummary>("sales-summary", params);
export const getItemWiseSales = (params: ReportFilterParams) => getReport<ItemWiseSales>("item-wise", params);
export const getCategoryWiseSales = (params: ReportFilterParams) =>
  getReport<CategoryWiseSales>("category-wise", params);
export const getTaxSummary = (params: ReportFilterParams) => getReport<TaxSummary>("tax-summary", params);
export const getWaiterWiseSales = (params: ReportFilterParams) => getReport<WaiterSales>("waiter-wise", params);
export const getCashierWiseSales = (params: ReportFilterParams) => getReport<CashierSales>("cashier-wise", params);
export const getWaiterIncentive = (params: ReportFilterParams) =>
  getReport<WaiterIncentive>("waiter-incentive", params);
export const getCashierIncentive = (params: ReportFilterParams) =>
  getReport<CashierIncentive>("cashier-incentive", params);
export const getZReport = (reportDate: string, locationId?: string) =>
  getReport<ZReport>("z-report", { report_date: reportDate, location_id: locationId });

// Report endpoints double as their own export — same path, `export=<format>` query
// param switches the response from JSON to a file download (gated server-side against
// the tenant's plan).
export async function downloadReportExport(
  reportPath: string,
  params: Record<string, string | undefined>,
  format: ExportFormat,
): Promise<void> {
  const response = await api.get(`/api/v1/reports/${reportPath}`, {
    params: { ...params, export: format },
    responseType: "blob",
  });
  const disposition = String(response.headers["content-disposition"] ?? "");
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? `${reportPath}.${format}`;

  const url = window.URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
