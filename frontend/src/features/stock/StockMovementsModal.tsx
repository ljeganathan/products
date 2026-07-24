import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { listStockMovements } from "@/api/stock";
import { Modal } from "@/components/ui/Modal";
import type { Stock } from "@/types/stock";

export interface StockMovementsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stock: Stock | null;
}

export function StockMovementsModal({ open, onOpenChange, stock }: StockMovementsModalProps) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["stock-movements", stock?.item_id],
    queryFn: () => listStockMovements({ item_id: stock?.item_id, page_size: 50 }),
    enabled: open && !!stock,
  });

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("stock.movementsTitle")}
      description={stock?.item_name_en}
      className="max-w-lg"
    >
      {isLoading && <p className="text-sm text-slate-500">{t("common.loading")}</p>}
      {!isLoading && (data?.items.length ?? 0) === 0 && (
        <p className="text-sm text-slate-500">{t("stock.noMovements")}</p>
      )}
      {!isLoading && (data?.items.length ?? 0) > 0 && (
        <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
          {data?.items.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2.5 text-sm">
              <div>
                <p className="font-medium text-slate-800">{t(`stock.reasons.${m.reason}`)}</p>
                <p className="text-slate-500">{new Date(m.created_at).toLocaleString("en-IN")}</p>
              </div>
              <span className={m.change_qty > 0 ? "font-semibold text-success-600" : "font-semibold text-danger-600"}>
                {m.change_qty > 0 ? "+" : ""}
                {m.change_qty}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
