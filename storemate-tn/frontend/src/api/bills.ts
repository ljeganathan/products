import { apiClient } from "@/api/client";
import type {
  Bill,
  BillCreate,
  BillPrintPayload,
  BillSearchResponse,
  ResumeBillResponse,
} from "@/types/bill";

export async function createBill(payload: BillCreate): Promise<Bill> {
  const { data } = await apiClient.post<Bill>("/bills", payload);
  return data;
}

export interface SearchBillsParams {
  page?: number;
  page_size?: number;
  store_id?: string;
  bill_number?: number;
  date_from?: string;
  date_to?: string;
  cashier_id?: string;
  customer_phone?: string;
  status?: string;
}

export async function searchBills(params: SearchBillsParams = {}): Promise<BillSearchResponse> {
  const { data } = await apiClient.get<BillSearchResponse>("/bills", { params });
  return data;
}

export async function getBill(billId: string): Promise<Bill> {
  const { data } = await apiClient.get<Bill>(`/bills/${billId}`);
  return data;
}

export async function resumeBill(billId: string): Promise<ResumeBillResponse> {
  const { data } = await apiClient.post<ResumeBillResponse>(`/bills/${billId}/resume`);
  return data;
}

export async function printBill(billId: string): Promise<BillPrintPayload> {
  const { data } = await apiClient.post<BillPrintPayload>(`/bills/${billId}/print`);
  return data;
}

export async function cancelBill(billId: string): Promise<Bill> {
  const { data } = await apiClient.post<Bill>(`/bills/${billId}/cancel`);
  return data;
}
