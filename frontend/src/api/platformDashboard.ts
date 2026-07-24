import { apiClient } from "@/api/client";
import type { PlatformDashboard } from "@/types/platformDashboard";

export async function getPlatformDashboard(): Promise<PlatformDashboard> {
  const { data } = await apiClient.get<PlatformDashboard>("/platform/dashboard");
  return data;
}
