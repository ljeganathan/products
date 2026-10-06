import { api } from "@/lib/api";

// Phase 28 + Cashfree — a hotel's own gateway credentials, one set per provider. The backend
// never returns the secrets, only whether they are set.
export type OnlinePaymentProvider = "razorpay" | "cashfree";

export interface OnlinePaymentProviderStatus {
  provider: OnlinePaymentProvider;
  configured: boolean;
  enabled: boolean;
  key_id: string | null;
  has_secret: boolean;
  has_webhook_secret: boolean;
  environment: "sandbox" | "production" | null;
  is_test_mode: boolean;
  webhook_url: string;
}

export interface OnlinePaymentSettings {
  available: boolean;
  enabled: boolean;
  // The provider taking payments right now (Razorpay when none is enabled).
  provider: OnlinePaymentProvider;
  auth_mode: string;
  key_id: string | null;
  has_secret: boolean;
  has_webhook_secret: boolean;
  is_test_mode: boolean;
  webhook_url: string;
  providers: OnlinePaymentProviderStatus[];
}

export interface OnlinePaymentSettingsInput {
  provider: OnlinePaymentProvider;
  key_id?: string;
  key_secret?: string;
  webhook_secret?: string;
  environment?: "sandbox" | "production";
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

export async function testOnlinePaymentConnection(
  provider: OnlinePaymentProvider,
): Promise<{ ok: boolean; is_test_mode: boolean }> {
  return (
    await api.post<{ ok: boolean; is_test_mode: boolean }>(
      "/api/v1/settings/online-payments/test",
      undefined,
      { params: { provider } },
    )
  ).data;
}
