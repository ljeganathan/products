import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";

import { formatINR } from "@/lib/utils";
import { me } from "@/modules/auth/authApi";
import {
  type Bill,
  type BillDiscountInput,
  type BillPaymentInput,
  createBill,
  previewBill,
  reprintBill,
} from "@/modules/pos/billsApi";
import type { Order } from "@/modules/pos/posApi";

interface BillingModalProps {
  order: Order;
  initialPaymentMethod: "upi" | "cash" | "card";
  onClose: () => void;
  onFinalized: () => void;
}

const PAYMENT_METHODS = [
  { code: "upi", label: "UPI" },
  { code: "cash", label: "Cash" },
  { code: "card", label: "Card" },
] as const;

const DISCOUNT_TYPE_LABELS: Record<string, string> = {
  flat_percent: "Flat %",
  item_level: "Item-level",
  coupon: "Coupon code",
};

const AMOUNT_TOLERANCE = 0.01;

export function BillingModal({ order, initialPaymentMethod, onClose, onFinalized }: BillingModalProps) {
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const allowedDiscountTypes = (meData?.features?.discount_types as unknown as string[] | undefined) ?? [
    "flat_percent",
  ];

  const [discountType, setDiscountType] = useState<string>("");
  const [percent, setPercent] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [itemAmounts, setItemAmounts] = useState<Record<string, string>>({});

  const [payments, setPayments] = useState<BillPaymentInput[]>([
    { method: initialPaymentMethod, amount: 0 },
  ]);
  const [finalizedBill, setFinalizedBill] = useState<Bill | null>(null);
  const [error, setError] = useState<string | null>(null);

  const discount: BillDiscountInput | null = useMemo(() => {
    if (!discountType) return null;
    if (discountType === "flat_percent") {
      const value = Number(percent);
      return value > 0 ? { type: "flat_percent", percent: value } : null;
    }
    if (discountType === "coupon") {
      return couponCode.trim() ? { type: "coupon", coupon_code: couponCode.trim() } : null;
    }
    // item_level
    const amounts: Record<string, number> = {};
    for (const [lineId, raw] of Object.entries(itemAmounts)) {
      const value = Number(raw);
      if (value > 0) amounts[lineId] = value;
    }
    return Object.keys(amounts).length > 0 ? { type: "item_level", item_amounts: amounts } : null;
  }, [discountType, percent, couponCode, itemAmounts]);

  // Coupon codes are typed character-by-character, so the raw `discount` above is
  // invalid for most of that typing — debounce what actually drives the preview
  // request so the UI doesn't flash a "couldn't calculate totals" error on every
  // keystroke before the full code is in.
  const [debouncedDiscount, setDebouncedDiscount] = useState(discount);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedDiscount(discount), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(discount)]);

  const {
    data: preview,
    isLoading: previewLoading,
    isError: previewError,
  } = useQuery({
    queryKey: ["bill-preview", order.id, debouncedDiscount],
    queryFn: () => previewBill({ order_id: order.id, discount: debouncedDiscount }),
    enabled: !finalizedBill,
  });

  // Once totals are known, default the (first) payment row to the full grand total —
  // still fully editable for a genuine split.
  const grandTotal = preview?.grand_total ?? 0;
  const paymentsTotal = payments.reduce((sum, p) => sum + (Number.isFinite(p.amount) ? p.amount : 0), 0);
  const balanced = Math.abs(paymentsTotal - grandTotal) <= AMOUNT_TOLERANCE;

  function syncSinglePaymentToGrandTotal(total: number) {
    setPayments((prev) => (prev.length === 1 ? [{ ...prev[0], amount: total }] : prev));
  }

  const finalizeMutation = useMutation({
    mutationFn: () => createBill({ order_id: order.id, discount, payments }),
    onSuccess: (bill) => setFinalizedBill(bill),
    onError: (err) =>
      setError(axios.isAxiosError(err) ? String(err.response?.data?.detail ?? err.message) : "Billing failed"),
  });

  const reprintMutation = useMutation({
    mutationFn: () => reprintBill(finalizedBill!.id),
    onSuccess: (bill) => setFinalizedBill(bill),
  });

  function updatePayment(index: number, patch: Partial<BillPaymentInput>) {
    setPayments((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  if (finalizedBill) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-pos">
          <h2 className="mb-1 text-lg font-extrabold text-veg">✅ Bill {finalizedBill.bill_number}</h2>
          <p className="mb-3 text-xs text-ink-faint">
            {finalizedBill.printed
              ? "Sent to the bill printer."
              : "No bill printer registered for this location — nothing was printed."}
          </p>
          <div className="mb-4 rounded-lg bg-surface-2 px-3.5 py-3 text-sm">
            <Row label="Subtotal" value={finalizedBill.subtotal} />
            {finalizedBill.discount_amount > 0 && (
              <Row label="Discount" value={-finalizedBill.discount_amount} />
            )}
            <Row label="CGST" value={finalizedBill.cgst_amount} />
            <Row label="SGST" value={finalizedBill.sgst_amount} />
            <Row label="Round Off" value={finalizedBill.round_off_amount} signed />
            <div className="mt-1.5 flex items-center justify-between border-t border-dashed border-border pt-1.5 text-base font-extrabold">
              <span>Grand Total</span>
              <span className="tabular-nums">{formatINR(finalizedBill.grand_total)}</span>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => reprintMutation.mutate()}
              disabled={reprintMutation.isPending}
              className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-surface-2 disabled:opacity-50"
            >
              {reprintMutation.isPending ? "Printing…" : "🖨 Reprint"}
            </button>
            <button
              type="button"
              onClick={onFinalized}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-accent-foreground"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-3 text-lg font-extrabold">🧾 Finalize Bill</h2>

        {allowedDiscountTypes.length > 0 && (
          <div className="mb-3 rounded-lg border border-border p-3">
            <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Discount
            </label>
            <select
              value={discountType}
              onChange={(e) => setDiscountType(e.target.value)}
              className="mb-2 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm"
            >
              <option value="">No discount</option>
              {allowedDiscountTypes.map((t) => (
                <option key={t} value={t}>
                  {DISCOUNT_TYPE_LABELS[t] ?? t}
                </option>
              ))}
            </select>

            {discountType === "flat_percent" && (
              <input
                type="number"
                min={0}
                max={100}
                placeholder="Percent off (e.g. 10)"
                value={percent}
                onChange={(e) => setPercent(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm"
              />
            )}
            {discountType === "coupon" && (
              <input
                type="text"
                placeholder="Coupon code"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm uppercase"
              />
            )}
            {discountType === "item_level" && (
              <ul className="flex flex-col gap-1.5">
                {order.items
                  .filter((line) => line.id)
                  .map((line) => (
                    <li key={line.id} className="flex items-center justify-between gap-2 text-xs">
                      <span className="min-w-0 flex-1 truncate">{line.name_en}</span>
                      <input
                        type="number"
                        min={0}
                        max={line.line_total}
                        placeholder="₹0"
                        value={itemAmounts[line.id!] ?? ""}
                        onChange={(e) =>
                          setItemAmounts((prev) => ({ ...prev, [line.id!]: e.target.value }))
                        }
                        className="w-20 rounded-md border border-border bg-background px-2 py-1 text-right"
                      />
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}

        <div className="mb-3 rounded-lg bg-surface-2 px-3.5 py-3 text-sm">
          {previewLoading && <p className="text-ink-faint">Calculating…</p>}
          {previewError && <p className="text-chili">Couldn't calculate totals — try again.</p>}
          {preview && (
            <>
              <Row label="Subtotal" value={preview.subtotal} />
              {preview.discount_amount > 0 && <Row label="Discount" value={-preview.discount_amount} />}
              <Row label="CGST" value={preview.cgst_amount} />
              <Row label="SGST" value={preview.sgst_amount} />
              <Row label="Round Off" value={preview.round_off_amount} signed />
              <div className="mt-1.5 flex items-center justify-between border-t border-dashed border-border pt-1.5 text-base font-extrabold">
                <span>Grand Total</span>
                <span className="tabular-nums">{formatINR(preview.grand_total)}</span>
              </div>
            </>
          )}
        </div>

        <div className="mb-3">
          <div className="mb-1.5 flex items-center justify-between">
            <label className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">Payment</label>
            {preview && (
              <button
                type="button"
                onClick={() => syncSinglePaymentToGrandTotal(preview.grand_total)}
                className="text-[10px] font-bold text-accent hover:underline"
              >
                Fill full amount
              </button>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            {payments.map((payment, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <select
                  value={payment.method}
                  onChange={(e) => updatePayment(i, { method: e.target.value as BillPaymentInput["method"] })}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-xs font-bold"
                >
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m.code} value={m.code}>
                      {m.label}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  min={0}
                  value={payment.amount || ""}
                  onChange={(e) => updatePayment(i, { amount: Number(e.target.value) })}
                  className="flex-1 rounded-md border border-border bg-background px-2.5 py-1.5 text-right text-sm tabular-nums"
                />
                {payments.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setPayments((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-chili"
                    aria-label="Remove payment"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() => setPayments((prev) => [...prev, { method: "cash", amount: 0 }])}
              className="self-start text-[11px] font-bold text-accent hover:underline"
            >
              + Split payment
            </button>
          </div>
          {preview && !balanced && (
            <p className="mt-1.5 text-[11px] font-semibold text-chili">
              Payments total {formatINR(paymentsTotal)} — must equal {formatINR(preview.grand_total)}
            </p>
          )}
        </div>

        {error && (
          <p role="alert" className="mb-3 rounded-md bg-chili-soft px-3 py-2 text-xs font-semibold text-chili">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => finalizeMutation.mutate()}
            disabled={!preview || !balanced || finalizeMutation.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-accent-foreground disabled:opacity-40"
          >
            {finalizeMutation.isPending ? "Finalizing…" : "Confirm & Bill"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, signed }: { label: string; value: number; signed?: boolean }) {
  const display = signed && value >= 0 ? `+${formatINR(value)}` : formatINR(value);
  return (
    <div className="flex items-center justify-between py-0.5 text-ink-soft">
      <span>{label}</span>
      <span className="tabular-nums font-bold text-foreground">{display}</span>
    </div>
  );
}
