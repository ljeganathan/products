import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { History, Lock, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { adjustStock, listLowStock, listStock } from "@/api/stock";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, type Column } from "@/components/ui/Table";
import { StockAdjustModal } from "@/features/stock/StockAdjustModal";
import { StockMovementsModal } from "@/features/stock/StockMovementsModal";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { Stock, StockMovementReason } from "@/types/stock";
import { getApiErrorMessage } from "@/utils/apiError";
import { stockStatusVariant } from "@/utils/stockStatus";

export interface StockTableProps {
  mode: "all" | "low-stock";
  canAdjust: boolean;
}

export function StockTable({ mode, canAdjust }: StockTableProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const storeId = useAuthStore((s) => s.user?.store_id ?? undefined);
  const [page, setPage] = useState(1);
  const [adjustingStock, setAdjustingStock] = useState<Stock | null>(null);
  const [movementsStock, setMovementsStock] = useState<Stock | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const queryKey = [mode === "all" ? "stock" : "low-stock", page, storeId];
  const { data, isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: () =>
      mode === "all"
        ? listStock({ page, page_size: 20, store_id: storeId })
        : listLowStock({ page, page_size: 20, store_id: storeId }),
    retry: (failureCount, err) => isAxiosError(err) && err.response?.status !== 403 && failureCount < 3,
  });

  const isUpgradeRequired = isError && isAxiosError(error) && error.response?.status === 403;
  if (isUpgradeRequired) {
    return (
      <EmptyState
        icon={Lock}
        title={t("stock.lowStockUpgradeTitle")}
        description={t("stock.lowStockUpgradeBody")}
        action={
          <Button asChild>
            <Link to="/settings">{t("stock.upgradePlanCta")}</Link>
          </Button>
        }
      />
    );
  }

  async function handleAdjust(changeQty: number, reason: StockMovementReason) {
    if (!adjustingStock) return;
    setIsSubmitting(true);
    try {
      await adjustStock({ item_id: adjustingStock.item_id, change_qty: changeQty, reason });
      await queryClient.invalidateQueries({ queryKey: ["stock"] });
      await queryClient.invalidateQueries({ queryKey: ["low-stock"] });
      await queryClient.invalidateQueries({ queryKey: ["stock-for-items"] });
      setAdjustingStock(null);
      toast("success", t("stock.adjustSuccess"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("stock.adjustError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  function statusLabel(s: Stock): string {
    if (s.quantity_on_hand <= 0) return t("stock.outOfStock");
    if (s.quantity_on_hand <= s.reorder_level) return t("stock.lowStock");
    return t("stock.inStock");
  }

  const columns: Column<Stock>[] = [
    {
      key: "item",
      header: t("items.name"),
      render: (s) => (
        <div>
          <p className="font-medium text-slate-900">{s.item_name_en}</p>
          <p className="text-sm text-slate-500">{s.item_name_ta}</p>
        </div>
      ),
    },
    { key: "barcode", header: t("items.barcode"), render: (s) => s.barcode ?? "—" },
    { key: "qty", header: t("stock.quantity"), render: (s) => s.quantity_on_hand },
    { key: "reorder", header: t("items.reorderLevel"), render: (s) => s.reorder_level },
    {
      key: "status",
      header: t("common.status"),
      render: (s) => (
        <Badge variant={stockStatusVariant(s.quantity_on_hand, s.reorder_level)}>
          {statusLabel(s)}
        </Badge>
      ),
    },
    {
      key: "last_restocked",
      header: t("stock.lastRestocked"),
      render: (s) => (s.last_restocked_at ? new Date(s.last_restocked_at).toLocaleDateString("en-IN") : "—"),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (s) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMovementsStock(s)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("stock.movementsTitle")}
          >
            <History className="h-4 w-4" />
          </button>
          {canAdjust && (
            <button
              type="button"
              onClick={() => setAdjustingStock(s)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-brand-600 hover:bg-brand-50"
              aria-label={t("stock.adjustTitle")}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(s) => s.id}
        isLoading={isLoading}
        emptyMessage={mode === "low-stock" ? t("stock.noLowStock") : t("stock.empty")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <StockAdjustModal
        open={adjustingStock !== null}
        onOpenChange={(open) => !open && setAdjustingStock(null)}
        stock={adjustingStock}
        onSubmit={handleAdjust}
        isSubmitting={isSubmitting}
      />

      <StockMovementsModal
        open={movementsStock !== null}
        onOpenChange={(open) => !open && setMovementsStock(null)}
        stock={movementsStock}
      />
    </>
  );
}
