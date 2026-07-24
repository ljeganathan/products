import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/ui/PageHeader";
import { StockTable } from "@/features/stock/StockTable";
import { useAuthStore } from "@/store/authStore";

export default function LowStockPage() {
  const { t } = useTranslation();
  const role = useAuthStore((s) => s.user?.role);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("stock.lowStockTitle")} />
      <StockTable mode="low-stock" canAdjust={role === "admin"} />
    </div>
  );
}
