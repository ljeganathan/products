import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { DiscountType } from "@/types/bill";

export interface DiscountModalProps {
  open: boolean;
  title: string;
  initialType: DiscountType | null;
  initialValue: number | null;
  onOpenChange: (open: boolean) => void;
  onApply: (type: DiscountType | null, value: number | null) => void;
}

/** Shared by both F4 (bill discount) and F5 (line discount) — value is
 * entered in rupees/percent by the cashier and converted to the paise/
 * basis-points convention the API expects (see billingCalc.ts). */
export function DiscountModal({
  open,
  title,
  initialType,
  initialValue,
  onOpenChange,
  onApply,
}: DiscountModalProps) {
  const { t } = useTranslation();
  const [type, setType] = useState<DiscountType>("flat");
  const [amount, setAmount] = useState("");

  useEffect(() => {
    if (!open) return;
    setType(initialType ?? "flat");
    // Both flat (paise) and percent (basis points) use the same x100
    // convention, so the same conversion works for either when re-editing.
    setAmount(initialValue == null ? "" : (initialValue / 100).toString());
  }, [open, initialType, initialValue]);

  function handleApply() {
    const parsed = Number(amount);
    if (!amount || Number.isNaN(parsed) || parsed <= 0) {
      onApply(null, null);
      onOpenChange(false);
      return;
    }
    onApply(type, Math.round(parsed * 100));
    onOpenChange(false);
  }

  function handleClear() {
    onApply(null, null);
    onOpenChange(false);
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      footer={
        <>
          <Button variant="ghost" onClick={handleClear}>
            {t("pos.clearDiscount")}
          </Button>
          <Button variant="primary" onClick={handleApply}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setType("flat")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              type === "flat"
                ? "border-brand-600 bg-brand-600 text-white"
                : "border-slate-300 text-slate-700"
            }`}
          >
            {t("pos.discountFlat")}
          </button>
          <button
            type="button"
            onClick={() => setType("percent")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              type === "percent"
                ? "border-brand-600 bg-brand-600 text-white"
                : "border-slate-300 text-slate-700"
            }`}
          >
            {t("pos.discountPercent")}
          </button>
        </div>
        <Input
          type="number"
          min="0"
          step="0.01"
          autoFocus
          label={type === "flat" ? t("pos.discountAmountLabel") : t("pos.discountPercentLabel")}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleApply();
          }}
        />
      </div>
    </Modal>
  );
}
