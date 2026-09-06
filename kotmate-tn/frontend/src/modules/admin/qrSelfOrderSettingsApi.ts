import { api } from "@/lib/api";

export async function updateQrSelfOrderSetting(enabled: boolean): Promise<{ enabled: boolean }> {
  return (await api.patch<{ enabled: boolean }>("/api/v1/settings/qr-self-order", { enabled })).data;
}
