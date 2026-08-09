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
}

export async function sendOrderToKot(orderId: string): Promise<{ ticket_number: string }> {
  return (await api.post<{ ticket_number: string }>("/api/v1/kot", { order_id: orderId })).data;
}

export async function listActiveKotTickets(): Promise<ActiveKotTicket[]> {
  return (await api.get<ActiveKotTicket[]>("/api/v1/kot/tickets/active")).data;
}

export async function updateKotTicketStatus(
  ticketId: string,
  status: "preparing" | "ready",
): Promise<ActiveKotTicket> {
  return (await api.patch<ActiveKotTicket>(`/api/v1/kot/tickets/${ticketId}/status`, { status })).data;
}
