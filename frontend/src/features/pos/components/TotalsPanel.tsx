import { Tag } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import type { CalcTotals } from "@/utils/billingCalc";
import { formatPaise } from "@/utils/money";
import type { PaymentMode } from "@/types/bill";

export interface TotalsPanelProps {
  totals: CalcTotals;
  paymentMode: PaymentMode;
  onPaymentModeChange: (mode: PaymentMode) => void;
  onOpenBillDiscount: () => void;
  onHold: () => void;
  onFinalize: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
  disabled: boolean;
}

const PAYMENT_MODES: PaymentMode[] = ["cash", "card", "upi", "split"];

export function TotalsPanel({
  totals,
  paymentMode,
  onPaymentModeChange,
  onOpenBillDiscount,
  onHold,
  onFinalize,
  onCancel,
  isSubmitting,
  disabled,
}: TotalsPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="flex w-full flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 lg:w-80">
      <div className="space-y-1.5 text-sm">
        <Row label={t("pos.subtotal")} value={formatPaise(totals.subtotalPaise)} />
        {totals.discountPaise > 0 && (
          <Row label={t("pos.discount")} value={`-${formatPaise(totals.discountPaise)}`} tone="brand" />
        )}
        <Row label={t("pos.cgst")} value={formatPaise(totals.cgstPaise)} />
        <Row label={t("pos.sgst")} value={formatPaise(totals.sgstPaise)} />
        {totals.roundOffPaise !== 0 && (
          <Row
            label={t("pos.roundOff")}
            value={`${totals.roundOffPaise > 0 ? "+" : ""}${formatPaise(totals.roundOffPaise)}`}
          />
        )}
        <div className="my-2 border-t border-slate-200" />
        <Row label={t("pos.total")} value={formatPaise(totals.totalPaise)} tone="total" />
      </div>

      <Button variant="outline" onClick={onOpenBillDiscount} disabled={disabled}>
        <Tag className="h-4 w-4" />
        {t("pos.billDiscount")} (F4)
      </Button>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700">
          {t("pos.paymentMode")}
        </label>
        <div className="grid grid-cols-2 gap-1.5">
          {PAYMENT_MODES.map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => onPaymentModeChange(mode)}
              disabled={disabled}
              className={`h-11 min-w-0 truncate rounded-lg border px-2 text-sm font-medium capitalize transition-colors ${
                paymentMode === mode
                  ? "border-brand-600 bg-brand-600 text-white"
                  : "border-slate-300 text-slate-700 hover:bg-slate-50"
              }`}
            >
              {t(`pos.paymentModes.${mode}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto flex flex-col gap-2">
        <Button variant="outline" onClick={onHold} disabled={disabled || isSubmitting}>
          {t("pos.holdBill")} (F8)
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={onFinalize}
          isLoading={isSubmitting}
          disabled={disabled}
        >
          {t("pos.finalizeBill")} (F10)
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={disabled || isSubmitting}>
          {t("pos.cancelBill")} (Esc)
        </Button>
      </div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "brand" | "total" }) {
  return (
    <div className="flex items-center justify-between">
      <span className={tone === "total" ? "text-base font-semibold text-slate-900" : "text-slate-600"}>
        {label}
      </span>
      <span
        className={
          tone === "total"
            ? "text-lg font-bold text-slate-900"
            : tone === "brand"
              ? "font-medium text-brand-600"
              : "font-medium text-slate-800"
        }
      >
        {value}
      </span>
    </div>
  );
}
