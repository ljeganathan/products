export type InvoiceStatus = "pending" | "paid" | "failed" | "void";

export interface Invoice {
  id: string;
  tenant_id: string;
  tenant_name: string;
  subscription_id: string;
  amount_paise: number;
  gst_paise: number;
  status: InvoiceStatus;
  invoice_number: string;
  issued_at: string;
  paid_at: string | null;
}

export interface InvoiceGenerateRequest {
  subscription_id: string;
}

export interface InvoiceStatusUpdate {
  status: InvoiceStatus;
}
