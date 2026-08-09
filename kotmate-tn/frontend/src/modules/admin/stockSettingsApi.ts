import { api } from "@/lib/api";

export async function updateStockManagementSetting(enabled: boolean): Promise<{ enabled: boolean }> {
  return (await api.patch<{ enabled: boolean }>("/api/v1/settings/stock-management", { enabled })).data;
}
