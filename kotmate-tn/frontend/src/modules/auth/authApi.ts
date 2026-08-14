import { api } from "@/lib/api";
import type { Role } from "@/modules/auth/authStore";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: Role;
  tenant_id: string | null;
  login_id: string;
}

export async function login(userId: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/api/v1/auth/login", {
    user_id: userId,
    password,
  });
  return data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function logout(): Promise<void> {
  await api.post("/api/v1/auth/logout");
}

// The backend returns the tenant's active plan's raw `features` JSONB as-is — most
// values are booleans (e.g. `qr_upi`, `kds`), but some are strings (`tax_mode`,
// `reports`) or string arrays (`discount_types`, `export_formats`). Callers narrow the
// specific key they read rather than assuming every value is a boolean.
export type PlanFeatures = Record<string, boolean | string | string[] | undefined>;

export interface MeResponse {
  login_id: string;
  role: Role;
  tenant_id: string | null;
  tenant_code: string | null;
  company_name: string | null;
  plan_code: string | null;
  max_users: number | null;
  max_locations: number | null;
  features: PlanFeatures | null;
  // Effective stock-quantity-tracking state (tenant toggle AND plan has the feature —
  // always true on plans without the feature, since that predates plan-gating and
  // never changed for them). The single flag to check for POS/KOT badges and the
  // Item Master "Track stock count" checkbox's editability.
  stock_tracking_enabled: boolean;
  // Tenant toggle for Tamil labels on the POS category rail/strip only — item buttons
  // still always show both languages (CLAUDE.md §9). Not plan-gated.
  show_tamil_categories: boolean;
}

export async function me(): Promise<MeResponse> {
  return (await api.get<MeResponse>("/api/v1/auth/me")).data;
}
