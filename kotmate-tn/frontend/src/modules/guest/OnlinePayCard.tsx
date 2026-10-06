import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

import { formatINR } from "@/lib/utils";
import {
  type GuestCreatedPayment,
  type GuestOnlinePaymentInfo,
  createGuestPayment,
  getGuestPaymentStatus,
} from "@/modules/guest/guestApi";

// Razorpay's two browser scripts. `razorpay.js` (custom checkout) can launch a specific UPI
// app straight from the page; `checkout.js` (standard checkout) is Razorpay's own popup with
// UPI ID / QR / card / netbanking, used as the fallback. Both are loaded on demand, only when
// the customer actually taps Pay, so guests who never pay never fetch them.
const CUSTOM_SCRIPT = "https://checkout.razorpay.com/v1/razorpay.js";
const STANDARD_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";
// Razorpay wants an email on UPI intent payments; the guest flow never asks for one.
const PLACEHOLDER_EMAIL = "no-reply@kotmatetn.in";
// Cashfree's JS SDK. Its checkout lists every UPI app, card and netbanking on one screen, so
// Cashfree has no separate Google Pay / PhonePe buttons.
const CASHFREE_SCRIPT = "https://sdk.cashfree.com/js/v3/cashfree.js";

interface CashfreeCheckout {
  checkout: (options: { paymentSessionId: string; redirectTarget?: string }) => Promise<unknown>;
}
type CashfreeFactory = (options: { mode: "sandbox" | "production" }) => CashfreeCheckout;

function cashfreeFactory(): CashfreeFactory {
  return (window as unknown as { Cashfree: CashfreeFactory }).Cashfree;
}

interface RazorpayInstance {
  open?: () => void;
  on: (event: string, cb: (payload: { error?: { description?: string; code?: string } }) => void) => void;
  createPayment: (data: Record<string, unknown>, options: { app: string }) => void;
}
type RazorpayCtor = new (options: Record<string, unknown>) => RazorpayInstance;

const scriptCache = new Map<string, Promise<void>>();
function loadScript(src: string): Promise<void> {
  const cached = scriptCache.get(src);
  if (cached) return cached;
  const promise = new Promise<void>((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.async = true;
    el.onload = () => resolve();
    el.onerror = () => {
      scriptCache.delete(src);
      reject(new Error("Couldn't load the payment screen — check your connection and try again."));
    };
    document.head.appendChild(el);
  });
  scriptCache.set(src, promise);
  return promise;
}

function razorpayCtor(): RazorpayCtor {
  return (window as unknown as { Razorpay: RazorpayCtor }).Razorpay;
}

type Phase = "idle" | "starting" | "waiting" | "paid" | "failed";
type Method = "gpay" | "phonepe" | "standard";

const POLL_MS = 2500;
const POLL_GIVE_UP_MS = 4 * 60 * 1000;

function errorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export function OnlinePayCard({
  info,
  total,
  tokenLabel,
  onPaid,
  onSessionEnded,
}: {
  info: GuestOnlinePaymentInfo;
  total: number;
  tokenLabel: string;
  onPaid: () => void;
  onSessionEnded: () => void;
}) {
  const [phase, setPhase] = useState<Phase>(info.paid ? "paid" : "idle");
  const [message, setMessage] = useState<string | null>(null);
  const [gaveUp, setGaveUp] = useState(false);
  // Only a payment that actually started can have deducted money — a failure while
  // creating the order (network, bad configuration) must not mention refunds.
  const [refundNote, setRefundNote] = useState(false);
  const [reference, setReference] = useState<string | null>(info.reference);
  const startedAt = useRef(0);
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

  const checkStatus = useCallback(async () => {
    try {
      const status = await getGuestPaymentStatus();
      if (status.status === "paid") {
        setReference(status.reference);
        setPhase("paid");
        onPaid();
      } else if (status.status === "failed") {
        setMessage(status.failure_reason ?? "The payment didn't go through.");
        setRefundNote(true);
        setPhase("failed");
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 404) onSessionEnded();
    }
  }, [onPaid, onSessionEnded]);

  // While waiting, ask our own server (which asks Razorpay) — never trust the browser's
  // "success" callback on its own — and re-check the moment the customer returns from
  // their UPI app.
  useEffect(() => {
    if (phase !== "waiting") return;
    const timer = setInterval(() => {
      if (Date.now() - startedAt.current > POLL_GIVE_UP_MS) {
        clearInterval(timer);
        setGaveUp(true);
        return;
      }
      void checkStatus();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void checkStatus();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [phase, checkStatus]);

  async function pay(method: Method) {
    setMessage(null);
    setRefundNote(false);
    setGaveUp(false);
    setPhase("starting");
    let created: GuestCreatedPayment;
    try {
      created = await createGuestPayment();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        // Already paid (e.g. a slow return from the UPI app) — just confirm and show it.
        await checkStatus();
        return;
      }
      setMessage(errorMessage(err, "Couldn't start the payment — please try again."));
      setPhase("failed");
      return;
    }

    const contact = created.customer_phone ? `+91${created.customer_phone}` : undefined;
    startedAt.current = Date.now();
    try {
      if (created.provider === "cashfree") {
        if (!created.payment_session_id) throw new Error("Couldn't start the payment — please try again.");
        await loadScript(CASHFREE_SCRIPT);
        const cashfree = cashfreeFactory()({
          mode: created.environment === "production" ? "production" : "sandbox",
        });
        setPhase("waiting");
        // Cashfree's checkout resolves when the guest closes it or finishes. Either way the
        // status poll is what confirms the payment, so re-check with our own server.
        void cashfree
          .checkout({ paymentSessionId: created.payment_session_id, redirectTarget: "_modal" })
          .catch(() => undefined)
          .then(() => checkStatus());
        return;
      }

      if (method === "standard") {
        await loadScript(STANDARD_SCRIPT);
        const checkout = new (razorpayCtor())({
          key: created.key_id,
          amount: created.amount_paise,
          currency: created.currency,
          order_id: created.provider_order_id,
          name: created.hotel_name,
          description: created.description,
          prefill: { name: created.customer_name ?? undefined, contact },
          theme: { color: "#1f7a55" },
          handler: () => void checkStatus(),
          modal: { ondismiss: () => void checkStatus() },
        });
        checkout.open?.();
        setPhase("waiting");
        return;
      }

      await loadScript(CUSTOM_SCRIPT);
      const rzp = new (razorpayCtor())({ key: created.key_id });
      rzp.on("payment.success", () => void checkStatus());
      rzp.on("payment.error", (payload) => {
        const code = payload?.error?.code ?? "";
        setRefundNote(code !== "intent_no_apps_error");
        setMessage(
          code === "intent_no_apps_error"
            ? "That app isn't available on this phone — try another option below."
            : (payload?.error?.description ?? "The payment didn't go through."),
        );
        setPhase("failed");
      });
      rzp.createPayment(
        {
          amount: created.amount_paise,
          method: "upi",
          contact,
          email: PLACEHOLDER_EMAIL,
          order_id: created.provider_order_id,
        },
        { app: method },
      );
      setPhase("waiting");
    } catch (err) {
      setMessage(errorMessage(err, "Couldn't open the payment screen — please try again."));
      setPhase("failed");
    }
  }

  if (phase === "paid") {
    return (
      <div className="mt-4 flex flex-col items-center gap-2 rounded-xl border border-border bg-surface p-5 text-center shadow-pos">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-veg/15 text-2xl font-black text-veg">✓</div>
        <p className="text-lg font-black">Payment received</p>
        <p className="text-xs text-ink-faint">
          {formatINR(info.paid_amount ?? total)} paid online{reference ? ` · ${reference}` : ""}
        </p>
        <p className="mt-2 text-[11px] font-bold uppercase tracking-wide text-ink-faint">Your order</p>
        <p className="font-mono text-4xl font-black leading-none">{tokenLabel}</p>
        <p className="mt-1 rounded-lg bg-surface-2 px-3 py-2 text-xs text-ink-soft">
          Show this at the counter when your order is ready.
        </p>
      </div>
    );
  }

  const busy = phase === "starting" || phase === "waiting";

  return (
    <div className="mt-4 rounded-xl border border-border bg-surface p-4 shadow-pos">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-extrabold uppercase tracking-wide text-ink-faint">Pay {formatINR(total)}</h2>
        {info.is_test_mode && (
          <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-extrabold uppercase text-gold">
            Test mode · no real money
          </span>
        )}
      </div>

      {phase === "waiting" ? (
        <div className="flex flex-col items-center gap-2 py-3 text-center" role="status">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-surface-3 border-t-accent" />
          <p className="text-sm font-bold">Confirming your payment…</p>
          <p className="text-xs text-ink-faint">Finish paying in your UPI app, then come back to this page.</p>
          {gaveUp && (
            <button
              type="button"
              onClick={() => void checkStatus()}
              className="mt-1 rounded-lg border border-border px-4 py-2 text-xs font-bold hover:bg-surface-2"
            >
              Check payment status
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setPhase("idle");
              setMessage(null);
            }}
            className="text-xs text-ink-faint underline"
          >
            Cancel and choose another way
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {phase === "failed" && message && (
            <p role="alert" className="rounded-lg bg-chili-soft px-3 py-2 text-xs font-semibold text-chili">
              {message}
              {refundNote && " If money was deducted, your bank refunds it automatically."}
            </p>
          )}
          {isMobile && info.provider !== "cashfree" && (
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void pay("gpay")}
                className="rounded-xl bg-accent py-3.5 text-sm font-extrabold text-accent-foreground disabled:opacity-50"
              >
                Google Pay
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void pay("phonepe")}
                className="rounded-xl bg-accent py-3.5 text-sm font-extrabold text-accent-foreground disabled:opacity-50"
              >
                PhonePe
              </button>
            </div>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => void pay("standard")}
            className={
              isMobile
                ? "rounded-xl border border-border py-3 text-sm font-bold hover:bg-surface-2 disabled:opacity-50"
                : "rounded-xl bg-accent py-3.5 text-sm font-extrabold text-accent-foreground disabled:opacity-50"
            }
          >
            {phase === "starting" ? "Starting…" : isMobile ? "Other UPI app, card or netbanking" : `Pay ${formatINR(total)}`}
          </button>
          <p className="text-center text-[11px] text-ink-faint">
            🔒 Secured by {info.provider === "cashfree" ? "Cashfree" : "Razorpay"}
          </p>
        </div>
      )}
    </div>
  );
}
