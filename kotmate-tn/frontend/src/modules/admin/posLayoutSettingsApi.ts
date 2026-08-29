import { api } from "@/lib/api";

export async function updatePosLayoutSetting(layout: "default" | "guided"): Promise<{ pos_layout: string }> {
  return (
    await api.patch<{ pos_layout: string }>("/api/v1/settings/pos-layout", { pos_layout: layout })
  ).data;
}

export async function updateWaiterMandatorySetting(enabled: boolean): Promise<{ enabled: boolean }> {
  return (await api.patch<{ enabled: boolean }>("/api/v1/settings/waiter-mandatory", { enabled })).data;
}
