import { apiClient } from "@/api/client";
import type { MaintenanceStatus, PlatformSettings, PlatformSettingsUpdate } from "@/types/platformSettings";

export async function getPlatformSettings(): Promise<PlatformSettings> {
  const { data } = await apiClient.get<PlatformSettings>("/platform/settings");
  return data;
}

export async function updatePlatformSettings(
  payload: PlatformSettingsUpdate,
): Promise<PlatformSettings> {
  const { data } = await apiClient.patch<PlatformSettings>("/platform/settings", payload);
  return data;
}

export async function getMaintenanceStatus(): Promise<MaintenanceStatus> {
  const { data } = await apiClient.get<MaintenanceStatus>("/platform/maintenance-status");
  return data;
}
