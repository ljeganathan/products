import { useTranslation } from "react-i18next";

import type { StoreTotal } from "@/types/dashboard";
import { cn } from "@/utils/cn";
import { formatPaise } from "@/utils/money";

export interface StoreTotalsTableProps {
  data: StoreTotal[];
  selectedStoreId: string | null;
  onSelectStore: (storeId: string | null) => void;
}

/** Pro Max store switcher: click a row to scope the whole dashboard to that
 * store, or "All stores" for the consolidated view. A table, not a chart —
 * per-store totals are exact figures an owner compares line by line, not a
 * trend to eyeball. */
export function StoreTotalsTable({ data, selectedStoreId, onSelectStore }: StoreTotalsTableProps) {
  const { t } = useTranslation();
  const consolidatedTotal = data.reduce((sum, s) => sum + s.total_paise, 0);
  const consolidatedBills = data.reduce((sum, s) => sum + s.bill_count, 0);

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-2 font-medium">{t("dashboard.store")}</th>
            <th className="px-4 py-2 font-medium">{t("dashboard.sales")}</th>
            <th className="px-4 py-2 font-medium">{t("dashboard.bills")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <tr
            role="button"
            tabIndex={0}
            onClick={() => onSelectStore(null)}
            className={cn(
              "cursor-pointer",
              selectedStoreId === null ? "bg-brand-50" : "hover:bg-slate-50",
            )}
          >
            <td className="px-4 py-2.5 font-medium text-slate-900">
              {t("dashboard.allStores")}
            </td>
            <td className="px-4 py-2.5">{formatPaise(consolidatedTotal)}</td>
            <td className="px-4 py-2.5">{consolidatedBills}</td>
          </tr>
          {data.map((s) => (
            <tr
              key={s.store_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectStore(s.store_id)}
              className={cn(
                "cursor-pointer",
                selectedStoreId === s.store_id ? "bg-brand-50" : "hover:bg-slate-50",
              )}
            >
              <td className="px-4 py-2.5 text-slate-800">{s.store_name}</td>
              <td className="px-4 py-2.5">{formatPaise(s.total_paise)}</td>
              <td className="px-4 py-2.5">{s.bill_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
