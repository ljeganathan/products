import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getMaintenanceStatus } from "@/api/platformSettings";
import { useAuthStore } from "@/store/authStore";

/** Polled by every tenant-facing layout (AppLayout, PosLayout) — never
 * rendered for product_owner, since a maintenance window is about the
 * tenant-facing app, not the platform console itself. */
export function MaintenanceBanner() {
  const { t } = useTranslation();
  const role = useAuthStore((s) => s.user?.role);

  const { data } = useQuery({
    queryKey: ["maintenance-status"],
    queryFn: () => getMaintenanceStatus(),
    refetchInterval: 60_000,
    enabled: role !== "product_owner",
  });

  if (role === "product_owner" || !data?.maintenance_mode) return null;

  return (
    <div className="flex items-center gap-2 bg-warning-100 px-4 py-2 text-sm font-medium text-warning-800">
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{data.maintenance_message || t("maintenance.defaultMessage")}</span>
    </div>
  );
}
