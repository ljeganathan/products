import type { BillPrintJob } from "@/modules/pos/billsApi";
import { api } from "@/lib/api";

// Phase 08's KOT endpoints: POST /api/v1/kot, GET /api/v1/kot/tickets/active,
// PATCH /api/v1/kot/tickets/{id}/status.

export interface ActiveKotTicketItem {
  name_en: string;
  name_ta: string | null;
  quantity: number;
}

export interface ActiveKotTicket {
  id: string;
  ticket_number: string;
  order_id: string;
  table_number: string | null;
  party_label: string | null;
  section_name_en: string;
  status: string;
  created_at: string;
  items: ActiveKotTicketItem[];
  // True only for a ticket created via Guided POS's combined "KOT + Bill" action —
  // its order is already billed, so the UI shouldn't offer to bill it again.
  order_billed_via_kot: boolean;
  // The finalized bill's number, set whenever order_billed_via_kot is true.
  bill_number: string | null;
}

export interface KotSendResult {
  ticket_number: string;
  printed: boolean;
  // usb/local_agent KOT printers only get rendered bytes back — see BillPrintJob.
  print_job: BillPrintJob | null;
  // Set only when a network/wifi KOT printer was registered and the backend's direct
  // socket send to it failed — a message safe to show the cashier as-is.
  print_error: string | null;
}

export async function sendOrderToKot(orderId: string): Promise<KotSendResult> {
  return (await api.post<KotSendResult>("/api/v1/kot", { order_id: orderId })).data;
}

export async function listActiveKotTickets(locationId?: string): Promise<ActiveKotTicket[]> {
  return (
    await api.get<ActiveKotTicket[]>("/api/v1/kot/tickets/active", {
      params: locationId ? { location_id: locationId } : undefined,
    })
  ).data;
}

export async function updateKotTicketStatus(
  ticketId: string,
  status: "preparing" | "ready",
): Promise<ActiveKotTicket> {
  return (await api.patch<ActiveKotTicket>(`/api/v1/kot/tickets/${ticketId}/status`, { status })).data;
}

// Dismisses a "bill already printed" ticket from the KOT Tickets screen/popup.
export async function clearBilledKotTicket(ticketId: string): Promise<ActiveKotTicket> {
  return (await api.post<ActiveKotTicket>(`/api/v1/kot/tickets/${ticketId}/clear`)).data;
}
