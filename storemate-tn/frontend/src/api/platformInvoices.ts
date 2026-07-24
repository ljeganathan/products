import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { Invoice, InvoiceGenerateRequest, InvoiceStatusUpdate } from "@/types/invoice";

export interface ListInvoicesParams {
  page?: number;
  page_size?: number;
  tenant_id?: string;
  status?: string;
}

export async function listInvoices(
  params: ListInvoicesParams = {},
): Promise<PaginatedResponse<Invoice>> {
  const { data } = await apiClient.get<PaginatedResponse<Invoice>>("/platform/invoices", {
    params,
  });
  return data;
}

export async function generateInvoice(payload: InvoiceGenerateRequest): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>("/platform/invoices/generate", payload);
  return data;
}

export async function updateInvoiceStatus(
  id: string,
  payload: InvoiceStatusUpdate,
): Promise<Invoice> {
  const { data } = await apiClient.patch<Invoice>(`/platform/invoices/${id}`, payload);
  return data;
}
