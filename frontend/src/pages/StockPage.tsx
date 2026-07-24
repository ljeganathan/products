import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { StockTable } from "@/features/stock/StockTable";
import { useAuthStore } from "@/store/authStore";

export default function StockPage() {
  const { t } = useTranslation();
  const role = useAuthStore((s) => s.user?.role);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("stock.title")}
        actions={
          <Button variant="outline" asChild>
            <Link to="/stock/low-stock">
              <AlertTriangle className="h-4 w-4" />
              {t("stock.viewLowStock")}
            </Link>
          </Button>
        }
      />
      <StockTable mode="all" canAdjust={role === "admin"} />
    </div>
  );
}
