import { api } from "@/lib/api";
import type { BillPrintJob } from "@/modules/pos/billsApi";

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
  // Item's current category — rows arrive pre-grouped category-major (categories by
  // total revenue descending, items within a category by their own revenue descending).
  category_id: string;
  category_name_en: string;
  category_name_ta: string | null;
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

export interface PosOperatorSalesRow {
  pos_user_id: string;
  login_id: string;
  name: string;
  bill_count: number;
  net_sale_value: number;
}
export interface PosOperatorSales {
  rows: PosOperatorSalesRow[];
  total_net_sale_value: number;
}

export interface PosOperatorIncentiveRow {
  pos_user_id: string;
  login_id: string;
  name: string;
  net_sale_value: number;
  incentive_amount: number;
}
export interface PosOperatorIncentive {
  rows: PosOperatorIncentiveRow[];
  total_incentive_amount: number;
}

export interface ItemListPriceOverride {
  section_id: string;
  section_name_en: string;
  price: number;
}
export interface ItemListRow {
  item_id: string;
  item_code: string | null;
  name_en: string;
  name_ta: string | null;
  category_id: string;
  category_name_en: string;
  category_name_ta: string | null;
  base_price: number;
  price_overrides: ItemListPriceOverride[];
}
export interface ItemList {
  rows: ItemListRow[];
  total_items: number;
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
export const getPosOperatorWiseSales = (params: ReportFilterParams) =>
  getReport<PosOperatorSales>("pos-operator-wise", params);
export const getPosOperatorIncentive = (params: ReportFilterParams) =>
  getReport<PosOperatorIncentive>("pos-operator-incentive", params);
export const getZReport = (reportDate: string, locationId?: string) =>
  getReport<ZReport>("z-report", { report_date: reportDate, location_id: locationId });
// Item master data, not date/location scoped (items aren't location-scoped) — see
// report_service.item_list.
export const getItemList = () => getReport<ItemList>("item-list", {});

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

export interface ReportPrintParams {
  report_type: string;
  date_from?: string;
  date_to?: string;
  report_date?: string;
  location_id?: string;
}

// Pro Max only (plan feature AND tenant's own "Enable report printing" toggle,
// Settings > Preferences) — plain ESC/POS-safe text, not the PDF/Excel/CSV export
// above, since a thermal/dot-matrix printer can't render a PDF.
export interface ReportPrintResult {
  printed: boolean;
  print_job: BillPrintJob | null;
  print_error: string | null;
}

export async function printReport(params: ReportPrintParams): Promise<ReportPrintResult> {
  return (await api.post<ReportPrintResult>("/api/v1/reports/print", params)).data;
}
