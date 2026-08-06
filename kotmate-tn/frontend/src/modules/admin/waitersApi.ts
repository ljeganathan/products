import { api } from "@/lib/api";

export interface Waiter {
  id: string;
  location_id: string;
  waiter_number: string;
  name: string;
  phone: string | null;
  incentive_rate: number | null;
  user_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface WaiterCreatePayload {
  location_id: string;
  waiter_number: string;
  name: string;
  phone?: string;
  incentive_rate?: number | null;
  user_id?: string | null;
}

export interface WaiterUpdatePayload extends Partial<WaiterCreatePayload> {
  is_active?: boolean;
}

export async function listWaiters(): Promise<Waiter[]> {
  return (await api.get<Waiter[]>("/api/v1/waiters")).data;
}

// Resolves the logged-in waiter's own Waiter Master row, if a tenant_admin has linked
// one — POS (Phase 07) uses this to auto-lock the waiter selector to themself.
export async function getMyWaiterProfile(): Promise<Waiter | null> {
  return (await api.get<Waiter | null>("/api/v1/waiters/me")).data;
}

export async function createWaiter(payload: WaiterCreatePayload): Promise<Waiter> {
  return (await api.post<Waiter>("/api/v1/waiters", payload)).data;
}

export async function updateWaiter(id: string, payload: WaiterUpdatePayload): Promise<Waiter> {
  return (await api.patch<Waiter>(`/api/v1/waiters/${id}`, payload)).data;
}
