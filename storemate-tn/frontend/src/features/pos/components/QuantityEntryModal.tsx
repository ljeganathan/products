import { AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { Item } from "@/types/item";
import { formatPaise } from "@/utils/money";

export interface QuantityEntryModalProps {
  open: boolean;
  item: Item | null;
  /** undefined = stock not loaded yet, so no warning is shown. */
  availableQty: number | undefined;
  /** Qty of this item already sitting in the cart, added to what's typed
   * here when checking against availableQty. */
  currentCartQty: number;
  onOpenChange: (open: boolean) => void;
  onConfirm: (qty: number) => void;
}

/** Opens whenever an item is selected via search, manual entry, or barcode
 * scan — lets the cashier confirm/adjust the quantity before it lands in
 * the cart, and surfaces stock availability right at the point of entry
 * instead of only failing silently later. */
export function QuantityEntryModal({
  open,
  item,
  availableQty,
  currentCartQty,
  onOpenChange,
  onConfirm,
}: QuantityEntryModalProps) {
  const { t } = useTranslation();
  const [qty, setQty] = useState("1");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQty("1");
    // Select-all so a cashier who just wants the default can type over it
    // immediately, or hit Enter to accept 1 with zero extra keystrokes.
    requestAnimationFrame(() => inputRef.current?.select());
  }, [open]);

  const parsedQty = Number(qty);
  const isValid = qty !== "" && !Number.isNaN(parsedQty) && parsedQty > 0;

  const isOutOfStock = availableQty !== undefined && availableQty <= 0;
  const wouldExceedStock =
    availableQty !== undefined && isValid && currentCartQty + parsedQty > availableQty && !isOutOfStock;

  function handleConfirm() {
    if (!isValid) return;
    onConfirm(parsedQty);
  }

  if (!item) return null;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={item.name_en}
      description={item.name_ta}
      footer={
        <Button onClick={handleConfirm} disabled={!isValid}>
          {t("pos.addToCart")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between text-sm text-slate-600">
          <span>{formatPaise(item.selling_price_paise)} / {item.unit}</span>
          {availableQty !== undefined && (
            <span className={isOutOfStock ? "font-medium text-danger-600" : "text-slate-500"}>
              {t("pos.availableQty", { qty: availableQty })}
            </span>
          )}
        </div>

        <Input
          ref={inputRef}
          type="number"
          min="0"
          step="0.001"
          autoFocus
          label={t("pos.qtyLabel")}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleConfirm();
          }}
        />

        {isOutOfStock && (
          <div className="flex items-center gap-2 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-sm text-danger-700">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{t("pos.outOfStockWarning")}</span>
          </div>
        )}
        {!isOutOfStock && wouldExceedStock && (
          <div className="flex items-center gap-2 rounded-lg border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{t("pos.lowStockWarning", { qty: availableQty })}</span>
          </div>
        )}
      </div>
    </Modal>
  );
}
