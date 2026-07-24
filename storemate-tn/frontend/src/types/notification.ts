export type NotificationType = "low_stock" | "subscription" | "system";

export interface Notification {
  id: string;
  tenant_id: string;
  store_id: string;
  type: NotificationType;
  title: string;
  body: string;
  is_read: boolean;
  created_for_user_id: string | null;
  reference_id: string | null;
  created_at: string;
}
