import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import { formatINR } from "@/lib/utils";
import { me } from "@/modules/auth/authApi";
import {
  type Bill,
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

const AMOUNT_TOLERANCE = 0.01;

export function BillingModal({ order, initialPaymentMethod, onClose, onFinalized }: BillingModalProps) {
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const allowedDiscountTypes = (meData?.features?.discount_types as unknown as string[] | undefined) ?? [
    "flat_percent",
  ];
  const couponsEnabled = allowedDiscountTypes.includes("coupon");

  // Item-level and Flat discounts auto-apply from active discount rules — the cashier's
  // only input here is an optional coupon code.
  const [couponCode, setCouponCode] = useState("");

  const [payments, setPayments] = useState<BillPaymentInput[]>([
    { method: initialPaymentMethod, amount: 0 },
  ]);
  const [finalizedBill, setFinalizedBill] = useState<Bill | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Print-preview flow: when on, finalizing shows an exact print-layout simulation and
  // waits for an explicit "Print" click before actually dispatching to the printer.
  // Default off — the normal flow finalizes and prints in the same action, then closes
  // straight back to POS with no extra confirmation window.
  const [previewBeforePrint, setPreviewBeforePrint] = useState(false);

  // Coupon codes are typed character-by-character, so debounce what actually drives the
  // preview request so the UI doesn't flash a "couldn't calculate totals" error mid-type.
  const [debouncedCouponCode, setDebouncedCouponCode] = useState(couponCode);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedCouponCode(couponCode.trim()), 400);
    return () => clearTimeout(timer);
  }, [couponCode]);

  const {
    data: preview,
    isLoading: previewLoading,
    isError: previewError,
  } = useQuery({
    queryKey: ["bill-preview", order.id, debouncedCouponCode],
    queryFn: () => previewBill({ order_id: order.id, coupon_code: debouncedCouponCode || undefined }),
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

  // Payment defaults to the full grand total as soon as it's known — a single (non-split)
  // payment must equal the grand total to bill anyway, so there's no case where a
  // cashier wants it pre-filled with anything else (POS-28, replaces a manual "Fill full
  // amount" click). Splitting still works: adding a row takes it out of this sync.
  useEffect(() => {
    if (preview) syncSinglePaymentToGrandTotal(preview.grand_total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.grand_total]);

  const finalizeMutation = useMutation({
    mutationFn: () =>
      createBill({
        order_id: order.id,
        coupon_code: debouncedCouponCode || undefined,
        payments,
        skip_print: previewBeforePrint,
      }),
    onSuccess: (bill) => {
      if (previewBeforePrint) {
        // Show the print-layout simulation and wait for an explicit Print click.
        setFinalizedBill(bill);
      } else {
        // Already printed as part of finalize (skip_print=false) — no extra window,
        // straight back to POS.
        onFinalized();
      }
    },
    onError: (err) =>
      setError(axios.isAxiosError(err) ? String(err.response?.data?.detail ?? err.message) : "Billing failed"),
  });

  const printMutation = useMutation({
    mutationFn: () => reprintBill(finalizedBill!.id),
    onSuccess: () => onFinalized(),
  });

  useEffect(() => {
    function isTypingTarget(el: EventTarget | null): boolean {
      const tag = (el as HTMLElement | null)?.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        if (finalizedBill) onFinalized();
        else onClose();
      } else if (e.key === "Enter" && !isTypingTarget(e.target)) {
        e.preventDefault();
        if (!finalizedBill) {
          if (preview && balanced && !finalizeMutation.isPending) finalizeMutation.mutate();
        } else if (!printMutation.isPending) {
          printMutation.mutate();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [finalizedBill, preview, balanced, finalizeMutation, printMutation, onClose, onFinalized]);

  function updatePayment(index: number, patch: Partial<BillPaymentInput>) {
    setPayments((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  // Print-preview screen: an exact simulation of the printed bill layout (monospace,
  // same line structure as backend/app/printing/base.py's format_bill_text_lines), not
  // just an information summary — so the cashier can verify it before it hits paper.
  if (finalizedBill) {
    const discountSegments = finalizedBill.discount_note ? finalizedBill.discount_note.split("; ") : [];
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="max-h-[90vh] w-full max-w-xs overflow-y-auto rounded-2xl bg-surface p-4 shadow-pos">
          <p className="mb-2 text-center text-xs font-bold text-ink-faint">🖨 Print Preview</p>
          <div className="rounded-lg bg-white p-3 font-mono text-[11px] leading-relaxed text-black">
            <p className="text-center font-bold">Bill #{finalizedBill.bill_number}</p>
            {finalizedBill.table_number && (
              <p className="text-center">
                {finalizedBill.table_number}
                {finalizedBill.party_label ? ` ${finalizedBill.party_label}` : ""} ({finalizedBill.section_name_en})
              </p>
            )}
            <p className="my-1 border-t border-dashed border-black/40" />
            {finalizedBill.items.map((line) => (
              <div key={line.id ?? line.item_id}>
                <div className="flex justify-between">
                  <span className="truncate">
                    {line.quantity} x {line.name_en}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span />
                  <span>{formatINR(line.line_total)}</span>
                </div>
              </div>
            ))}
            <p className="my-1 border-t border-dashed border-black/40" />
            <Row label="Subtotal" value={finalizedBill.subtotal} mono />
            {discountSegments.map((seg, i) => (
              <div key={i} className="flex justify-between text-black/80">
                <span className="truncate">{seg}</span>
              </div>
            ))}
            <Row label="CGST" value={finalizedBill.cgst_amount} mono />
            <Row label="SGST" value={finalizedBill.sgst_amount} mono />
            <Row label="Round Off" value={finalizedBill.round_off_amount} signed mono />
            <div className="mt-1 flex items-center justify-between border-t border-dashed border-black/40 pt-1 font-bold">
              <span>Grand Total</span>
              <span>{formatINR(finalizedBill.grand_total)}</span>
            </div>
            <p className="my-1 border-t border-dashed border-black/40" />
            {finalizedBill.payments.map((p, i) => (
              <div key={i} className="flex justify-between">
                <span className="capitalize">{p.method}</span>
                <span>{formatINR(p.amount)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={onFinalized}
              className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-surface-2"
            >
              Skip / Close
            </button>
            <button
              type="button"
              onClick={() => printMutation.mutate()}
              disabled={printMutation.isPending}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-accent-foreground disabled:opacity-50"
            >
              {printMutation.isPending ? "Printing…" : "🖨 Print"}
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

        {couponsEnabled && (
          <div className="mb-3 rounded-lg border border-border p-3">
            <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Coupon Code
            </label>
            <input
              type="text"
              placeholder="Enter coupon code (optional)"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
              className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm uppercase"
            />
          </div>
        )}

        <div className="mb-3 rounded-lg bg-surface-2 px-3.5 py-3 text-sm">
          {previewLoading && <p className="text-ink-faint">Calculating…</p>}
          {previewError && <p className="text-chili">Couldn't calculate totals — try again.</p>}
          {preview && (
            <>
              <Row label="Subtotal" value={preview.subtotal} />
              {preview.discount_note ? (
                preview.discount_note.split("; ").map((seg, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 text-veg">
                    <span className="text-xs">{seg}</span>
                  </div>
                ))
              ) : (
                preview.discount_amount > 0 && <Row label="Discount" value={-preview.discount_amount} />
              )}
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
          <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wide text-ink-faint">
            Payment
          </label>
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
              className="min-h-[38px] rounded-lg border border-accent bg-accent-soft px-3 text-sm font-bold text-accent hover:bg-accent hover:text-accent-foreground"
            >
              + Split Payment
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

        <label className="mb-3 flex items-center gap-2 text-xs font-semibold text-ink-soft">
          <input
            type="checkbox"
            checked={previewBeforePrint}
            onChange={(e) => setPreviewBeforePrint(e.target.checked)}
          />
          Show print preview before printing
        </label>

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

function Row({ label, value, signed, mono }: { label: string; value: number; signed?: boolean; mono?: boolean }) {
  const display = signed && value >= 0 ? `+${formatINR(value)}` : formatINR(value);
  if (mono) {
    return (
      <div className="flex items-center justify-between">
        <span>{label}</span>
        <span>{display}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-between py-0.5 text-ink-soft">
      <span>{label}</span>
      <span className="tabular-nums font-bold text-foreground">{display}</span>
    </div>
  );
}
