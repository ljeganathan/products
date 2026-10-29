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
  // `redirectTarget` is "_modal" / "_self" / "_blank", or a DOM element for inline
  // rendering (kiosk, see below) — Cashfree's own SDK accepts all four.
  checkout: (options: { paymentSessionId: string; redirectTarget?: string | HTMLElement }) => Promise<unknown>;
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

// One payment button for every provider. The badge is a generic "UPI" mark rather than an app
// logo (see CLAUDE.md §9), and the caption names what the button does.
function UpiButton({
  caption,
  amount,
  disabled,
  onClick,
}: {
  caption: string;
  amount?: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-accent px-3 py-3 text-accent-foreground hover:opacity-90 disabled:opacity-50"
    >
      <span className="rounded bg-accent-foreground px-1.5 py-0.5 text-[10px] font-black tracking-wide text-accent">
        UPI
      </span>
      <span className="flex flex-col items-start leading-tight">
        <span className="text-sm font-extrabold">{amount ? `Pay ${amount}` : "Pay"}</span>
        <span className="text-[11px] font-semibold opacity-80">{caption}</span>
      </span>
    </button>
  );
}

function errorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export function OnlinePayCard({
  info,
  total,
  tokenLabel,
  kioskMode = false,
  onPaid,
  onSessionEnded,
}: {
  info: GuestOnlinePaymentInfo;
  total: number;
  tokenLabel: string;
  // An unattended kiosk screen is never the customer's own phone, so it must never try
  // to open an app-intent payment on itself — always the one checkout button that shows
  // a scannable QR (Razorpay/Cashfree's own checkout already does this by default on a
  // non-mobile-UA browser), never the Google Pay/PhonePe intent buttons below.
  kioskMode?: boolean;
  onPaid: (info: { amount: number | null; reference: string | null }) => void;
  onSessionEnded: () => void;
}) {
  const [phase, setPhase] = useState<Phase>(info.paid ? "paid" : "idle");
  const [message, setMessage] = useState<string | null>(null);
  const [gaveUp, setGaveUp] = useState(false);
  // Only a payment that actually started can have deducted money — a failure while
  // creating the order (network, bad configuration) must not mention refunds.
  const [refundNote, setRefundNote] = useState(false);
  const [reference, setReference] = useState<string | null>(info.reference);
  // Kiosk only: the QR image handed back directly by our own backend (either provider,
  // see `pay()` below), shown full-screen with no checkout widget at all.
  const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
  const startedAt = useRef(0);
  // Kiosk + Cashfree fallback only (its best-effort QR-channel call failed): Cashfree's
  // inline checkout renders itself into this element instead of a modal, when
  // `redirectTarget` is a DOM node rather than "_modal". Must already be mounted before
  // `pay()` runs, which it is — the kiosk render branch below returns this container
  // unconditionally, before the auto-pay effect ever fires.
  const cashfreeContainerRef = useRef<HTMLDivElement>(null);
  const isMobile = !kioskMode && /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

  const checkStatus = useCallback(async () => {
    try {
      const status = await getGuestPaymentStatus();
      if (status.status === "paid") {
        setReference(status.reference);
        setPhase("paid");
        onPaid({ amount: status.paid_amount ?? null, reference: status.reference ?? null });
      } else if (status.status === "failed") {
        setMessage(status.failure_reason ?? "The payment didn't go through.");
        setRefundNote(true);
        setPhase("failed");
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 404) onSessionEnded();
    }
  }, [onPaid, onSessionEnded]);

  // Kiosk only — opens the (UPI-restricted) checkout itself, the instant this card
  // appears, instead of waiting for a tap: nobody's there to read a row of payment
  // buttons on an unattended screen, so the only thing shown is the QR once the
  // checkout opens (see the `kioskMode` config.display/order_meta restrictions below).
  useEffect(() => {
    if (kioskMode && phase === "idle") void pay("standard");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kioskMode, phase]);

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
    setQrImageUrl(null);
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
      if (kioskMode && created.qr_image_url) {
        // Kiosk, either provider: our backend already has a ready-made QR image (Razorpay's
        // own standalone QR code, or Cashfree's best-effort QR-channel call) — no checkout
        // widget to open at all, just show the image itself, full screen (render branch below).
        setQrImageUrl(created.qr_image_url);
        setPhase("waiting");
        return;
      }

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
          .checkout({
            paymentSessionId: created.payment_session_id,
            // Kiosk: render inline into our own full-screen container instead of
            // Cashfree's fixed-size modal (order_meta already restricts this to UPI/QR —
            // see payment_gateway.py — so it's effectively just the QR, full screen).
            redirectTarget: kioskMode ? cashfreeContainerRef.current ?? "_modal" : "_modal",
          })
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
          // Kiosk only — restricts Razorpay's own checkout to a single UPI block,
          // hiding cards/netbanking/wallets entirely (documented `config.display`
          // customization: a lone block with show_default_blocks off). Nobody's
          // standing at a kiosk to tap through payment methods it can't actually use.
          ...(kioskMode
            ? {
                config: {
                  display: {
                    blocks: {
                      upi_only: { name: "Pay via UPI", instruments: [{ method: "upi" }] },
                    },
                    sequence: ["block.upi_only"],
                    preferences: { show_default_blocks: false },
                  },
                },
              }
            : {}),
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
          {kioskMode
            ? "Sent to the kitchen — remember your number and collect it when ready."
            : "Show this at the counter when your order is ready."}
        </p>
      </div>
    );
  }

  // Kiosk's entire pre-paid flow is a full-screen takeover, not the small card below — an
  // unattended screen needs the QR itself big enough to scan from arm's length, not a
  // card-sized image inside a payment-methods layout nobody there can even tap through.
  if (kioskMode) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-5 bg-white p-6 text-center">
        <h2 className="text-base font-extrabold uppercase tracking-wide text-ink-faint">
          Scan to pay {formatINR(total)}
        </h2>
        {phase === "failed" && message ? (
          <>
            <p role="alert" className="max-w-sm rounded-lg bg-chili-soft px-4 py-3 text-sm font-semibold text-chili">
              {message}
              {refundNote && " If money was deducted, your bank refunds it automatically."}
            </p>
            <button
              type="button"
              onClick={() => void pay("standard")}
              className="rounded-lg border border-border px-5 py-2.5 text-sm font-bold hover:bg-surface-2"
            >
              Try again
            </button>
          </>
        ) : qrImageUrl ? (
          <img
            src={qrImageUrl}
            alt="Scan this QR code with any UPI app to pay"
            className="h-[min(70vw,60vh)] w-[min(70vw,60vh)] object-contain"
          />
        ) : (
          // Razorpay before its QR image arrives, or Cashfree's inline-checkout fallback
          // (its QR-channel call failed) — Cashfree injects its own UI straight into this
          // element (`redirectTarget` in `pay()` above), already restricted server-side to
          // UPI/QR only.
          <div
            ref={cashfreeContainerRef}
            className="flex h-[min(70vw,60vh)] w-[min(70vw,60vh)] items-center justify-center"
          >
            {info.provider !== "cashfree" && (
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-surface-3 border-t-accent" />
            )}
          </div>
        )}
        {phase !== "failed" && (
          <p className="flex items-center gap-2 text-sm text-ink-faint">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-surface-3 border-t-accent" />
            Scan with any UPI app — the kitchen gets your order the moment it's paid.
          </p>
        )}
        {info.is_test_mode && (
          <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-extrabold uppercase text-gold">
            Test mode · no real money
          </span>
        )}
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
              <UpiButton
                disabled={busy}
                caption="Google Pay"
                onClick={() => void pay("gpay")}
              />
              <UpiButton
                disabled={busy}
                caption="PhonePe"
                onClick={() => void pay("phonepe")}
              />
            </div>
          )}
          <UpiButton
            disabled={busy}
            caption={
              phase === "starting"
                ? "Starting…"
                : isMobile && info.provider !== "cashfree"
                  ? "Other UPI app, card or netbanking"
                  : "UPI apps, cards & netbanking"
            }
            amount={isMobile ? undefined : formatINR(total)}
            onClick={() => void pay("standard")}
          />
          <p className="text-center text-[11px] text-ink-faint">
            🔒 Secured by {info.provider === "cashfree" ? "Cashfree" : "Razorpay"}
          </p>
        </div>
      )}
    </div>
  );
}
