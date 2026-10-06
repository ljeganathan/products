import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import { dispatchPrintJob } from "@/lib/printDispatch";
import { formatINR } from "@/lib/utils";
import { me } from "@/modules/auth/authApi";
import {
  type Bill,
  type BillPaymentInput,
  createBill,
  previewBill,
  reprintBill,
  sendKotAndFinalizeBill,
} from "@/modules/pos/billsApi";
import type { Order } from "@/modules/pos/posApi";

interface BillingModalProps {
  order: Order;
  initialPaymentMethod: "upi" | "cash" | "card" | "online";
  onClose: () => void;
  onFinalized: (printWarning?: string) => void;
  // "kot-and-bill" is Guided POS's non-seating combined action — same modal, same
  // preview/payment/print-preview flow, just finalizing via the atomic combined route
  // instead of a plain bill, and dispatching the kitchen ticket's own print job too.
  // Defaults to "bill" so every existing caller (Default layout) is unaffected.
  mode?: "bill" | "kot-and-bill";
}

const PAYMENT_METHODS = [
  { code: "upi", label: "UPI" },
  { code: "online", label: "Online" },
  { code: "cash", label: "Cash" },
  { code: "card", label: "Card" },
] as const;

const AMOUNT_TOLERANCE = 0.01;

// discount_note segments are "<rule name>: -₹X.XX" — split so the amount can be
// rendered right-aligned in its own column instead of trailing inline after a
// variable-length rule name.
function splitDiscountSegment(segment: string): [string, string] {
  const idx = segment.lastIndexOf(": ");
  return idx === -1 ? [segment, ""] : [segment.slice(0, idx), segment.slice(idx + 2)];
}

// FastAPI returns `detail` as a string for our own errors but as an array of
// {msg, loc} objects for request-validation (422) errors — String() on that array is
// what used to show a bare "[object Object]".
function billingErrorMessage(err: unknown): string {
  if (!axios.isAxiosError(err)) return "Billing failed";
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg ?? "Invalid input").join("; ");
  }
  return err.message;
}

function formatBillDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function BillingModal({
  order,
  initialPaymentMethod,
  onClose,
  onFinalized,
  mode = "bill",
}: BillingModalProps) {
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const allowedDiscountTypes = (meData?.features?.discount_types as unknown as string[] | undefined) ?? [
    "flat_percent",
  ];
  const couponsEnabled = allowedDiscountTypes.includes("coupon");

  // Item-level and Flat discounts auto-apply from active discount rules — the cashier's
  // only input here is an optional coupon code.
  const [couponCode, setCouponCode] = useState("");
  // Optional customer identity — prefilled once from the preview (a QR guest's own
  // name/phone), then owned by the cashier so later preview refetches (e.g. while typing
  // a coupon) never overwrite an edit.
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerPrefilled, setCustomerPrefilled] = useState(false);

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

  // A guest who already paid online is billed as "online" for exactly what they paid.
  const onlinePaid = preview?.online_paid_amount ?? null;

  function syncSinglePaymentToGrandTotal(total: number) {
    setPayments((prev) =>
      prev.length === 1
        ? [{ ...prev[0], amount: total, ...(onlinePaid !== null ? { method: "online" as const } : {}) }]
        : prev,
    );
  }

  // Payment defaults to the full grand total as soon as it's known — a single (non-split)
  // payment must equal the grand total to bill anyway, so there's no case where a
  // cashier wants it pre-filled with anything else (POS-28, replaces a manual "Fill full
  // amount" click). Splitting still works: adding a row takes it out of this sync.
  useEffect(() => {
    if (preview) syncSinglePaymentToGrandTotal(preview.grand_total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.grand_total]);

  useEffect(() => {
    if (preview && !customerPrefilled) {
      setCustomerName(preview.customer_name ?? "");
      setCustomerPhone(preview.customer_phone ?? "");
      setCustomerPrefilled(true);
    }
  }, [preview, customerPrefilled]);

  const finalizeMutation = useMutation({
    mutationFn: () =>
      (mode === "kot-and-bill" ? sendKotAndFinalizeBill : createBill)({
        order_id: order.id,
        coupon_code: debouncedCouponCode || undefined,
        customer_name: customerName.trim() || undefined,
        customer_phone: customerPhone.trim() || undefined,
        payments,
        skip_print: previewBeforePrint,
      }),
    onSuccess: async (bill) => {
      if (previewBeforePrint) {
        // Show the print-layout simulation and wait for an explicit Print click.
        setFinalizedBill(bill);
        return;
      }
      // Already dispatched server-side as part of finalize (skip_print=false) — for a
      // usb/local_agent printer that dispatch is just rendered bytes waiting on us to
      // forward them, so do that now before returning to POS. A network/wifi printer
      // was already attempted server-side; `print_error` carries why if it failed. The
      // combined route also fires a kitchen ticket in the same action — its own print
      // job (if any) is dispatched right alongside the bill's, silently when both
      // succeed; only a genuine warning from either half surfaces to the cashier.
      const billWarning = (await dispatchPrintJob(bill.print_job)) ?? bill.print_error ?? undefined;
      const kotWarning =
        mode === "kot-and-bill"
          ? ((await dispatchPrintJob(bill.kot_print_job ?? null)) ?? bill.kot_print_error ?? undefined)
          : undefined;
      const warning = [billWarning, kotWarning].filter(Boolean).join(" · ") || undefined;
      onFinalized(warning);
    },
    onError: (err) => setError(billingErrorMessage(err)),
  });

  const printMutation = useMutation({
    mutationFn: () => reprintBill(finalizedBill!.id),
    onSuccess: async (bill) => {
      const warning = (await dispatchPrintJob(bill.print_job)) ?? bill.print_error ?? undefined;
      onFinalized(warning);
    },
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
            <p className="text-center">{formatBillDateTime(finalizedBill.created_at)}</p>
            {finalizedBill.waiter_name && <p className="text-center">Waiter: {finalizedBill.waiter_name}</p>}
            {(finalizedBill.customer_name || finalizedBill.customer_phone) && (
              <p className="text-center">
                Customer: {[finalizedBill.customer_name, finalizedBill.customer_phone].filter(Boolean).join(" / ")}
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
            {discountSegments.map((seg, i) => {
              const [label, amount] = splitDiscountSegment(seg);
              return (
                <div key={i} className="flex justify-between text-black/80">
                  <span className="truncate">{label}</span>
                  <span>{amount}</span>
                </div>
              );
            })}
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
              onClick={() => onFinalized()}
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

  const inputClass = "min-w-0 rounded-md border border-border bg-background px-2.5 py-1.5 text-sm";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3">
      {/* dvh (not vh) so the modal is sized to the *visible* area on Android/iOS browsers,
          whose address bar otherwise pushes the bottom buttons off-screen. Header and
          button row are pinned; only the middle scrolls on a very short screen. */}
      <div className="flex max-h-[94dvh] w-full max-w-md flex-col rounded-2xl bg-surface shadow-pos">
        <h2 className="flex-none px-4 pb-2 pt-3.5 text-base font-extrabold">
          {mode === "kot-and-bill" ? "🍳🧾 Send to Kitchen & Finalize Bill" : "🧾 Finalize Bill"}
        </h2>

        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-4 pb-2">
          {preview && onlinePaid !== null && (
            <div className="rounded-lg bg-veg/10 px-3 py-2 text-xs font-semibold text-veg" role="status">
              ✓ Paid online {formatINR(onlinePaid)}
              {preview.online_payment_reference ? ` · ${preview.online_payment_reference}` : ""}
              {Math.abs(onlinePaid - preview.grand_total) > 0.01 && (
                <span className="mt-0.5 block text-chili">
                  The bill is now {formatINR(preview.grand_total)} — settle the difference with the customer.
                </span>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              maxLength={100}
              placeholder="Customer name (optional)"
              aria-label="Customer name (optional)"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className={inputClass}
            />
            <input
              type="tel"
              maxLength={20}
              placeholder="Phone (optional)"
              aria-label="Customer phone (optional)"
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              className={inputClass}
            />
            {couponsEnabled && (
              <input
                type="text"
                placeholder="Enter coupon code (optional)"
                aria-label="Coupon code"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                className={`${inputClass} col-span-2 uppercase`}
              />
            )}
          </div>

          <div className="rounded-lg bg-surface-2 px-3 py-2 text-[13px]">
            {previewLoading && <p className="text-ink-faint">Calculating…</p>}
            {previewError && <p className="text-chili">Couldn't calculate totals — try again.</p>}
            {preview && (
              <>
                <Row label="Subtotal" value={preview.subtotal} />
                {preview.discount_note ? (
                  preview.discount_note.split("; ").map((seg, i) => {
                    const [label, amount] = splitDiscountSegment(seg);
                    return (
                      <div key={i} className="flex items-center justify-between text-veg">
                        <span className="text-xs">{label}</span>
                        <span className="text-xs font-bold tabular-nums">{amount}</span>
                      </div>
                    );
                  })
                ) : (
                  preview.discount_amount > 0 && <Row label="Discount" value={-preview.discount_amount} />
                )}
                <Row label="CGST" value={preview.cgst_amount} />
                <Row label="SGST" value={preview.sgst_amount} />
                <Row label="Round Off" value={preview.round_off_amount} signed />
                <div className="mt-1 flex items-center justify-between border-t border-dashed border-border pt-1 text-base font-extrabold">
                  <span>Grand Total</span>
                  <span className="tabular-nums">{formatINR(preview.grand_total)}</span>
                </div>
              </>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {payments.map((payment, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <select
                  aria-label="Payment method"
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
                  aria-label="Payment amount"
                  value={payment.amount || ""}
                  onChange={(e) => updatePayment(i, { amount: Number(e.target.value) })}
                  className="min-w-0 flex-1 rounded-md border border-border bg-background px-2.5 py-1.5 text-right text-sm tabular-nums"
                />
                {payments.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setPayments((prev) => prev.filter((_, idx) => idx !== i))}
                    className="px-1 text-chili"
                    aria-label="Remove payment"
                  >
                    ✕
                  </button>
                )}
                {i === payments.length - 1 && (
                  <button
                    type="button"
                    onClick={() => setPayments((prev) => [...prev, { method: "cash", amount: 0 }])}
                    className="shrink-0 rounded-md border border-accent bg-accent-soft px-2.5 py-1.5 text-xs font-bold text-accent hover:bg-accent hover:text-accent-foreground"
                  >
                    + Split
                  </button>
                )}
              </div>
            ))}
            {preview && !balanced && (
              <p className="text-[11px] font-semibold text-chili">
                Payments total {formatINR(paymentsTotal)} — must equal {formatINR(preview.grand_total)}
              </p>
            )}
          </div>

          {error && (
            <p role="alert" className="rounded-md bg-chili-soft px-3 py-2 text-xs font-semibold text-chili">
              {error}
            </p>
          )}
        </div>

        <div className="flex flex-none items-center justify-between gap-2 border-t border-border px-4 py-2.5">
          <label className="flex items-center gap-1.5 text-[11px] font-semibold leading-tight text-ink-soft">
            <input
              type="checkbox"
              checked={previewBeforePrint}
              onChange={(e) => setPreviewBeforePrint(e.target.checked)}
            />
            Print preview
          </label>
          <div className="flex gap-2">
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
              {finalizeMutation.isPending
                ? "Finalizing…"
                : mode === "kot-and-bill"
                  ? "Confirm — KOT + Bill"
                  : "Confirm & Bill"}
            </button>
          </div>
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
    <div className="flex items-center justify-between text-ink-soft">
      <span>{label}</span>
      <span className="tabular-nums font-bold text-foreground">{display}</span>
    </div>
  );
}
