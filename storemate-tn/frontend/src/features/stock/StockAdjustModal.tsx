import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Stock, StockMovementReason } from "@/types/stock";

const REASONS: StockMovementReason[] = ["purchase", "adjustment", "return", "damage"];

export interface StockAdjustModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stock: Stock | null;
  onSubmit: (changeQty: number, reason: StockMovementReason) => Promise<void>;
  isSubmitting: boolean;
}

export function StockAdjustModal({
  open,
  onOpenChange,
  stock,
  onSubmit,
  isSubmitting,
}: StockAdjustModalProps) {
  const { t } = useTranslation();
  const [direction, setDirection] = useState<"add" | "remove">("add");
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState<StockMovementReason>("purchase");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDirection("add");
    setQty("");
    setReason("purchase");
    setError(null);
  }, [open]);

  async function handleSubmit() {
    const parsed = Number(qty);
    if (!qty || Number.isNaN(parsed) || parsed <= 0) {
      setError(t("stock.qtyRequired"));
      return;
    }
    setError(null);
    await onSubmit(direction === "add" ? parsed : -parsed, reason);
  }

  if (!stock) return null;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("stock.adjustTitle")}
      description={stock.item_name_en}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("stock.applyAdjustment")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-500">
          {t("stock.currentQty")}: <strong>{stock.quantity_on_hand}</strong>
        </p>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setDirection("add")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              direction === "add"
                ? "border-success-600 bg-success-600 text-white"
                : "border-slate-300 text-slate-700"
            }`}
          >
            {t("stock.addStock")}
          </button>
          <button
            type="button"
            onClick={() => setDirection("remove")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              direction === "remove"
                ? "border-danger-600 bg-danger-600 text-white"
                : "border-slate-300 text-slate-700"
            }`}
          >
            {t("stock.removeStock")}
          </button>
        </div>

        <Input
          type="number"
          min="0"
          step="0.001"
          label={t("stock.quantity")}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          error={error ?? undefined}
        />

        <Select
          label={t("stock.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value as StockMovementReason)}
        >
          {REASONS.map((r) => (
            <option key={r} value={r}>
              {t(`stock.reasons.${r}`)}
            </option>
          ))}
        </Select>
      </div>
    </Modal>
  );
}
