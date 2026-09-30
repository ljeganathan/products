import { api } from "@/lib/api";

// Phase 28 — a hotel's own Razorpay credentials. The backend never returns the secrets,
// only whether they are set.
export interface OnlinePaymentSettings {
  available: boolean;
  enabled: boolean;
  provider: string;
  auth_mode: string;
  key_id: string | null;
  has_secret: boolean;
  has_webhook_secret: boolean;
  is_test_mode: boolean;
  webhook_url: string;
}

export interface OnlinePaymentSettingsInput {
  key_id?: string;
  key_secret?: string;
  webhook_secret?: string;
  enabled?: boolean;
}

export async function getOnlinePaymentSettings(): Promise<OnlinePaymentSettings> {
  return (await api.get<OnlinePaymentSettings>("/api/v1/settings/online-payments")).data;
}

export async function saveOnlinePaymentSettings(
  payload: OnlinePaymentSettingsInput,
): Promise<OnlinePaymentSettings> {
  return (await api.put<OnlinePaymentSettings>("/api/v1/settings/online-payments", payload)).data;
}

export async function testOnlinePaymentConnection(): Promise<{ ok: boolean; is_test_mode: boolean }> {
  return (await api.post<{ ok: boolean; is_test_mode: boolean }>("/api/v1/settings/online-payments/test")).data;
}
