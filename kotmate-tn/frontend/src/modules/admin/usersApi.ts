import { api } from "@/lib/api";

// CLAUDE.md §5 — "kitchen" is labeled "KOT User" everywhere in UI copy; role code
// stays `kitchen` for backend/API/RLS continuity.
export type StaffRole = "tenant_admin" | "pos_user" | "waiter" | "kitchen";

export const STAFF_ROLE_LABELS: Record<StaffRole, string> = {
  tenant_admin: "Admin",
  pos_user: "Cashier",
  waiter: "Waiter",
  kitchen: "KOT User",
};

export interface TenantUser {
  id: string;
  user_id: string;
  local_handle: string;
  name: string;
  phone: string | null;
  role: StaffRole;
  incentive_rate: number | null;
  location_ids: string[];
  is_active: boolean;
  created_at: string;
}

export interface UserCreatePayload {
  local_handle: string;
  name: string;
  phone?: string;
  role: StaffRole;
  password: string;
  incentive_rate?: number | null;
  location_ids?: string[];
}

export interface UserUpdatePayload {
  name?: string;
  phone?: string;
  role?: StaffRole;
  incentive_rate?: number | null;
  location_ids?: string[];
  is_active?: boolean;
}

export interface SeatUsage {
  active_billable_users: number;
  max_users: number | null;
}

export async function listUsers(): Promise<TenantUser[]> {
  return (await api.get<TenantUser[]>("/api/v1/users")).data;
}

export async function createUser(payload: UserCreatePayload): Promise<TenantUser> {
  return (await api.post<TenantUser>("/api/v1/users", payload)).data;
}

export async function updateUser(id: string, payload: UserUpdatePayload): Promise<TenantUser> {
  return (await api.patch<TenantUser>(`/api/v1/users/${id}`, payload)).data;
}

export async function resetUserPassword(id: string, newPassword: string): Promise<void> {
  await api.post(`/api/v1/users/${id}/reset-password`, { new_password: newPassword });
}

export async function getSeatUsage(): Promise<SeatUsage> {
  return (await api.get<SeatUsage>("/api/v1/users/seat-usage")).data;
}
