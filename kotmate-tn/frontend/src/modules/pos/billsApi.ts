import { api } from "@/lib/api";

// Phase 09's billing endpoints: POST /api/v1/bills, POST /api/v1/bills/preview,
// GET /api/v1/bills (search), GET /api/v1/bills/{id}, POST /api/v1/bills/{id}/reprint.

export interface BillDiscountInput {
  type: "flat_percent" | "item_level" | "coupon";
  percent?: number | null;
  coupon_code?: string | null;
  item_amounts?: Record<string, number> | null;
}

export interface BillPaymentInput {
  method: "upi" | "cash" | "card";
  amount: number;
}

export interface BillItemLine {
  id: string | null;
  item_id: string;
  name_en: string;
  name_ta: string | null;
  unit_price: number;
  quantity: number;
  line_total: number;
}

export interface BillPayment {
  method: string;
  amount: number;
}

interface BillTotals {
  items: BillItemLine[];
  subtotal: number;
  discount_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  round_off_amount: number;
  grand_total: number;
  waiter_incentive_amount: number | null;
  cashier_incentive_amount: number | null;
}

export interface BillPreview extends BillTotals {
  order_id: string;
  payments: BillPayment[];
}

export interface Bill extends BillTotals {
  id: string;
  bill_number: string;
  order_id: string;
  location_id: string;
  table_id: string | null;
  table_number: string | null;
  section_id: string;
  section_name_en: string;
  waiter_id: string | null;
  waiter_name: string | null;
  party_label: string | null;
  pos_user_id: string;
  pos_user_login_id: string;
  status: string;
  payments: BillPayment[];
  printed: boolean;
  created_at: string;
}

export interface BillPreviewPayload {
  order_id: string;
  discount?: BillDiscountInput | null;
  line_tax_overrides?: Record<string, string> | null;
}

export interface BillCreatePayload extends BillPreviewPayload {
  payments: BillPaymentInput[];
  skip_print?: boolean;
}

export interface BillSearchParams {
  bill_number?: string;
  date_from?: string;
  date_to?: string;
  table_id?: string;
  waiter_id?: string;
  location_id?: string;
  section_id?: string;
  pos_user_id?: string;
}

export async function previewBill(payload: BillPreviewPayload): Promise<BillPreview> {
  return (await api.post<BillPreview>("/api/v1/bills/preview", payload)).data;
}

export async function createBill(payload: BillCreatePayload): Promise<Bill> {
  return (await api.post<Bill>("/api/v1/bills", payload)).data;
}

export async function listBills(params?: BillSearchParams): Promise<Bill[]> {
  return (await api.get<Bill[]>("/api/v1/bills", { params })).data;
}

export async function getBill(id: string): Promise<Bill> {
  return (await api.get<Bill>(`/api/v1/bills/${id}`)).data;
}

export async function reprintBill(id: string): Promise<Bill> {
  return (await api.post<Bill>(`/api/v1/bills/${id}/reprint`)).data;
}
