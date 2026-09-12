import axios from "axios";

import { API_BASE_URL } from "@/lib/api";
import type { Category } from "@/modules/admin/categoriesApi";
import type { Order, OrderLineInput } from "@/modules/pos/posApi";

// Deliberately its own axios instance and its own localStorage key — never the staff
// `api` client from lib/api.ts. That client's 401 handler clears the *staff* session
// and hard-redirects to /login, which would be exactly wrong here (and actively
// dangerous on a shared/kiosk device: it could wipe out a staff member's own logged-in
// session just because a guest's 3-hour QR session happened to expire in the same
// browser). A guest 401 here only ever means "this ordering session has ended" — the
// guest app handles that itself by asking to rescan, nothing more.
const GUEST_TOKEN_KEY = "kotmate_guest_token";

export const guestApi = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export function getGuestToken(): string | null {
  return localStorage.getItem(GUEST_TOKEN_KEY);
}

export function setGuestToken(token: string): void {
  localStorage.setItem(GUEST_TOKEN_KEY, token);
}

export function clearGuestToken(): void {
  localStorage.removeItem(GUEST_TOKEN_KEY);
}

guestApi.interceptors.request.use((config) => {
  const token = getGuestToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface GuestSession {
  guest_token: string;
  tenant_id: string;
  location_id: string;
  // Both null for a Takeaway session (Phase 26) — pickup_token/section_name_en are
  // set instead, shown where a table number would otherwise appear.
  table_id: string | null;
  table_number: string | null;
  pickup_token: string | null;
  section_name_en: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  order_id: string | null;
  status: "active" | "payment_claimed" | "closed";
}

// True for a Takeaway/non-seating session — every scan is its own independent order
// (never shared, never resumed), and the UI shows a pickup token instead of a table.
export function isTakeawaySession(session: GuestSession): boolean {
  return session.table_id === null;
}

export async function startGuestSession(qrToken: string): Promise<GuestSession> {
  const { data } = await guestApi.post<GuestSession>(`/api/v1/guest/sessions/${qrToken}`);
  setGuestToken(data.guest_token);
  return data;
}

export async function updateGuestProfile(payload: {
  customer_name?: string;
  customer_phone?: string;
}): Promise<GuestSession> {
  return (await guestApi.patch<GuestSession>("/api/v1/guest/sessions/me", payload)).data;
}

export interface GuestMenuItem {
  id: string;
  name_en: string;
  name_ta: string | null;
  category_id: string;
  price: number;
  item_code: string | null;
  image_url: string | null;
  is_top_seller: boolean;
  is_combo_tile: boolean;
  track_inventory: boolean;
  available_qty: number | null;
  is_active: boolean;
}

export async function getGuestMenu(): Promise<GuestMenuItem[]> {
  return (await guestApi.get<GuestMenuItem[]>("/api/v1/guest/menu")).data;
}

export async function getGuestCategories(): Promise<Category[]> {
  return (await guestApi.get<Category[]>("/api/v1/guest/categories")).data;
}

export async function getGuestTopSellers(): Promise<GuestMenuItem[]> {
  return (await guestApi.get<GuestMenuItem[]>("/api/v1/guest/top-sellers")).data;
}

export async function getGuestCart(): Promise<Order | null> {
  const { data } = await guestApi.get<Order | null>("/api/v1/guest/cart");
  return data;
}

export async function updateGuestCart(items: OrderLineInput[]): Promise<Order> {
  return (await guestApi.post<Order>("/api/v1/guest/cart", { items })).data;
}

export interface GuestKotSendResponse {
  id: string;
  ticket_number: string;
  order_id: string;
}

export async function sendGuestOrderToKitchen(): Promise<GuestKotSendResponse> {
  return (await guestApi.post<GuestKotSendResponse>("/api/v1/guest/send-kot")).data;
}

export interface GuestOrderStatusTicket {
  id: string;
  ticket_number: string;
  order_id: string;
  status: "new" | "preparing" | "ready";
  created_at: string;
  items: { name_en: string; name_ta: string | null; quantity: number }[];
}

export async function getGuestOrderStatus(): Promise<GuestOrderStatusTicket[]> {
  return (await guestApi.get<GuestOrderStatusTicket[]>("/api/v1/guest/order-status")).data;
}

export interface GuestBillPreview {
  order_id: string;
  items: { item_id: string; name_en: string; name_ta: string | null; quantity: number; line_total: number }[];
  subtotal: number;
  discount_amount: number;
  discount_note: string | null;
  cgst_amount: number;
  sgst_amount: number;
  round_off_amount: number;
  grand_total: number;
  upi_link: string | null;
}

export async function getGuestBillPreview(): Promise<GuestBillPreview> {
  return (await guestApi.get<GuestBillPreview>("/api/v1/guest/bill-preview")).data;
}

export async function requestGuestBill(): Promise<{ status: string }> {
  return (await guestApi.post<{ status: string }>("/api/v1/guest/request-bill")).data;
}
