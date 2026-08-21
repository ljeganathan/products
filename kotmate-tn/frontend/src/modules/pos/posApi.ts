import { api } from "@/lib/api";

export interface OrderLineInput {
  // Echoes OrderItemLine.id for a line that already exists on the order, so the backend
  // can match this input back to its exact row (compute_updated_lines) — omit for a
  // genuinely new line. Always omitted/undefined for a brand-new add so it can never be
  // mistaken for (and silently merged into) an existing — possibly already-KOT-sent —
  // row that happens to share the same item_id/notes.
  id?: string | null;
  item_id: string;
  quantity: number;
  notes?: string | null;
}

export interface OrderItemLine {
  id: string | null;
  item_id: string;
  name_en: string;
  name_ta: string | null;
  item_code: string | null;
  unit_price: number;
  quantity: number;
  notes: string | null;
  is_kot_sent: boolean;
  line_total: number;
  track_inventory: boolean;
  available_qty: number | null;
}

export interface Order {
  id: string;
  location_id: string;
  section_id: string;
  section_name_en: string;
  section_is_seating: boolean;
  table_id: string | null;
  table_number: string | null;
  waiter_id: string | null;
  waiter_name: string | null;
  pos_user_id: string;
  pos_user_login_id: string;
  status: "open" | "held" | "billed";
  hold_label: string | null;
  party_label: string | null;
  items: OrderItemLine[];
  subtotal: number;
  waiter_incentive_amount: number | null;
  cashier_incentive_amount: number | null;
  created_at: string;
}

export interface OrderPreview {
  order: Order;
  subtotal_changed: boolean;
}

export interface OrderCreatePayload {
  location_id: string;
  section_id: string;
  table_id?: string | null;
  waiter_id?: string | null;
  items: OrderLineInput[];
  hold_label?: string | null;
  party_label?: string | null;
}

export interface OrderUpdatePayload {
  section_id?: string;
  table_id?: string | null;
  waiter_id?: string | null;
  items?: OrderLineInput[];
  hold_label?: string | null;
  party_label?: string | null;
  status?: "open" | "held";
}

export async function createOrder(payload: OrderCreatePayload): Promise<Order> {
  return (await api.post<Order>("/api/v1/orders", payload)).data;
}

export async function getOrder(id: string): Promise<Order> {
  return (await api.get<Order>(`/api/v1/orders/${id}`)).data;
}

export async function listOrders(params?: {
  status?: string;
  location_id?: string;
  table_id?: string;
}): Promise<Order[]> {
  return (await api.get<Order[]>("/api/v1/orders", { params })).data;
}

export async function updateOrder(id: string, payload: OrderUpdatePayload): Promise<Order> {
  return (await api.patch<Order>(`/api/v1/orders/${id}`, payload)).data;
}

export async function previewOrderUpdate(id: string, payload: OrderUpdatePayload): Promise<OrderPreview> {
  return (await api.patch<OrderPreview>(`/api/v1/orders/${id}?dry_run=true`, payload)).data;
}

// --- Items (POS-facing reads) ---

export interface PosItem {
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

export async function listPosItems(params?: { category_id?: string }): Promise<PosItem[]> {
  return (await api.get<PosItem[]>("/api/v1/items", { params: { ...params, active_only: true } })).data;
}

export async function searchItems(q: string): Promise<PosItem[]> {
  return (await api.get<PosItem[]>("/api/v1/items/search", { params: { q } })).data;
}

export async function getItemByCode(code: string): Promise<PosItem> {
  return (await api.get<PosItem>(`/api/v1/items/by-code/${encodeURIComponent(code)}`)).data;
}

export async function listTopSellers(): Promise<PosItem[]> {
  return (await api.get<PosItem[]>("/api/v1/items/top-sellers")).data;
}

// --- Sections (POS table/section picker) ---

export interface PosSection {
  id: string;
  name_en: string;
  name_ta: string | null;
  is_seating: boolean;
  display_order: number;
}

export async function listPosSections(): Promise<PosSection[]> {
  return (await api.get<PosSection[]>("/api/v1/sections/pos")).data;
}
