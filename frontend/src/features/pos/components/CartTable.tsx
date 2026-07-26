import { Minus, Plus, Tag, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CartLine } from "@/store/cartStore";
import type { CalcLineResult } from "@/utils/billingCalc";
import { resolveItemName } from "@/utils/itemDisplayName";
import { formatPaise } from "@/utils/money";
import { cn } from "@/utils/cn";

export interface CartTableProps {
  lines: CartLine[];
  lineResults: CalcLineResult[];
  selectedIndex: number | null;
  showTamilItemNames: boolean;
  onSelect: (index: number) => void;
  onQtyChange: (index: number, qty: number) => void;
  onAdjustQty: (index: number, delta: number) => void;
  onRemove: (index: number) => void;
  onOpenDiscount: (index: number) => void;
}

export function CartTable({
  lines,
  lineResults,
  selectedIndex,
  showTamilItemNames,
  onSelect,
  onQtyChange,
  onAdjustQty,
  onRemove,
  onOpenDiscount,
}: CartTableProps) {
  const { t } = useTranslation();

  if (lines.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-slate-400">
        {t("pos.emptyCart")}
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white">
      <ul className="divide-y divide-slate-100">
        {lines.map((line, index) => {
          const result = lineResults[index];
          const isSelected = index === selectedIndex;
          return (
            <li
              key={`${line.itemId}-${index}`}
              onClick={() => onSelect(index)}
              className={cn(
                "flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors",
                isSelected ? "bg-brand-50" : "hover:bg-slate-50",
              )}
            >
              <div className="w-6 shrink-0 text-sm text-slate-400">{index + 1}</div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-slate-900">
                  {resolveItemName(line.nameEn, line.nameTa, showTamilItemNames)}
                </p>
                <p className="text-sm text-slate-500">
                  {formatPaise(line.unitPricePaise)} / {line.unit}
                  {result && result.discountPaise > 0 && (
                    <span className="ml-2 text-brand-600">
                      -{formatPaise(result.discountPaise)}
                    </span>
                  )}
                </p>
              </div>

              <div
                className="flex items-center gap-1 rounded-lg border border-slate-200"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  onClick={() => onAdjustQty(index, -1)}
                  className="flex h-11 w-11 items-center justify-center text-slate-600 hover:bg-slate-100"
                  aria-label={t("pos.decreaseQty")}
                >
                  <Minus className="h-4 w-4" />
                </button>
                <input
                  type="number"
                  value={line.qty}
                  onChange={(e) => onQtyChange(index, Number(e.target.value))}
                  className="h-11 w-16 border-x border-slate-200 text-center text-base focus:outline-none"
                  step="0.001"
                  min="0"
                />
                <button
                  type="button"
                  onClick={() => onAdjustQty(index, 1)}
                  className="flex h-11 w-11 items-center justify-center text-slate-600 hover:bg-slate-100"
                  aria-label={t("pos.increaseQty")}
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>

              <div className="w-24 shrink-0 text-right font-medium text-slate-900">
                {result ? formatPaise(result.lineTotalPaise) : ""}
              </div>

              <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  onClick={() => onOpenDiscount(index)}
                  className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
                  aria-label={t("pos.lineDiscount")}
                >
                  <Tag className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(index)}
                  className="flex h-11 w-11 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
                  aria-label={t("pos.removeLine")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
