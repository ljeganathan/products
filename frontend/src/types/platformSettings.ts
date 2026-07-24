export interface PlatformSettings {
  maintenance_mode: boolean;
  maintenance_message: string | null;
}

export interface PlatformSettingsUpdate {
  maintenance_mode?: boolean;
  maintenance_message?: string | null;
}

export interface MaintenanceStatus {
  maintenance_mode: boolean;
  maintenance_message: string | null;
}
