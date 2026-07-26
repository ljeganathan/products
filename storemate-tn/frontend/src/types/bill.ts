export type PaymentMode = "cash" | "card" | "upi" | "split";
export type BillStatus = "completed" | "held" | "cancelled";
export type DiscountType = "flat" | "percent";

export interface BillItemCreate {
  item_id: string;
  qty: number;
  discount_type?: DiscountType | null;
  /** paise for flat, basis points for percent (10.50% -> 1050). */
  discount_value?: number | null;
}

export interface BillCreate {
  store_id?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  payment_mode: PaymentMode;
  items: BillItemCreate[];
  bill_discount_type?: DiscountType | null;
  bill_discount_value?: number | null;
  hold?: boolean;
}

export interface BillItemOut {
  id: string;
  item_id: string;
  item_name_snapshot: string;
  qty: number;
  unit_price_paise: number;
  discount_paise: number;
  tax_profile_snapshot_json: { cgst_pct: number; sgst_pct: number; igst_pct: number };
  line_total_paise: number;
}

export interface Bill {
  id: string;
  tenant_id: string;
  store_id: string;
  bill_number: number;
  cashier_id: string;
  customer_name: string | null;
  customer_phone: string | null;
  subtotal_paise: number;
  discount_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  round_off_paise: number;
  total_paise: number;
  payment_mode: PaymentMode;
  status: BillStatus;
  printed_count: number;
  created_at: string;
  items: BillItemOut[];
}

export interface BillSearchResponse {
  items: Bill[];
  total: number;
  page: number;
  page_size: number;
  saved_bill_days: number;
  window_start: string | null;
  requested_from_clamped: boolean;
}

export interface ResumeBillResponse {
  store_id: string;
  customer_name: string | null;
  customer_phone: string | null;
  payment_mode: PaymentMode;
  items: BillItemCreate[];
}

export interface PrintPayloadItem {
  name: string;
  qty: number;
  unit_price_paise: number;
  discount_paise: number;
  line_total_paise: number;
}

export interface CompanySettings {
  id: string;
  tenant_id: string;
  store_id: string;
  legal_name: string;
  display_name: string;
  address: string;
  pincode: string | null;
  gstin: string | null;
  fssai_no: string | null;
  phone: string | null;
  logo_url: string | null;
  invoice_footer_text: string | null;
}

export interface BillPrintPayload {
  bill_number: number;
  created_at: string;
  cashier_name: string;
  customer_name: string | null;
  customer_phone: string | null;
  company: CompanySettings;
  items: PrintPayloadItem[];
  subtotal_paise: number;
  discount_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  round_off_paise: number;
  total_paise: number;
  payment_mode: PaymentMode;
}
