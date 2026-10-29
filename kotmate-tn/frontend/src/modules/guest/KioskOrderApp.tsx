import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useRef, useState } from "react";

import logoMark from "@/assets/logo-mark.png";
import { formatINR } from "@/lib/utils";
import { listLocations } from "@/modules/admin/locationsApi";
import { listSections } from "@/modules/admin/sectionsApi";
import { UserMenu } from "@/modules/auth/UserMenu";
import {
  BillTab,
  CartSheet,
  CenteredMessage,
  MenuTab,
  RequiredProfileScreen,
  StatusTab,
  toLineInputs,
} from "@/modules/guest/GuestOrderApp";
import {
  type GuestMenuItem,
  type GuestSession,
  getGuestCart,
  getGuestCategories,
  getGuestMenu,
  getGuestTopSellers,
  sendGuestOrderToKitchen,
  startKioskSession,
  updateGuestCart,
} from "@/modules/guest/guestApi";
import { TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import type { Order } from "@/modules/pos/posApi";

type Tab = "menu" | "status" | "bill";

const KIOSK_SETUP_KEY = "kotmate_kiosk_setup";
// Resets the kiosk back to a blank cart for the next customer a while after a
// successful payment — long enough for the current customer to read the pickup
// number, short enough that the next person isn't kept waiting on a stale screen.
// A "Done" button on the receipt screen lets an engaged customer skip the wait.
const AUTO_RESET_MS = 30000;

interface KioskSetup {
  locationId: string;
  sectionId: string;
}

function readKioskSetup(): KioskSetup | null {
  try {
    const raw = localStorage.getItem(KIOSK_SETUP_KEY);
    return raw ? (JSON.parse(raw) as KioskSetup) : null;
  } catch {
    return null;
  }
}

function writeKioskSetup(setup: KioskSetup): void {
  localStorage.setItem(KIOSK_SETUP_KEY, JSON.stringify(setup));
}

function errorDetail(err: unknown): string | undefined {
  if (axios.isAxiosError(err)) return err.response?.data?.detail as string | undefined;
  return undefined;
}

function isSessionEndedError(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 404;
}

// An unattended on-premise ordering screen (CLAUDE.md §5's "Kiosk" role) — logged in
// with its own staff login, which is used for exactly one call (startKioskSession) to
// mint a guest session; from then on this behaves exactly like the QR self-order app
// (GuestOrderApp.tsx) talking over that guest token, reusing its same sub-components,
// just without a table/QR to scan and with a few kiosk-only differences: both Payment
// Gateway and Cash are offered (production request — cash prints the bill immediately
// and waits for a POS operator to approve the kitchen ticket), a scannable QR instead
// of an app-intent button for online payment, and an automatic reset back to the idle
// "Order Here" screen once an order is paid for.
export function KioskOrderApp() {
  const [setup, setSetup] = useState<KioskSetup | null>(() => readKioskSetup());

  if (!setup) {
    return <KioskSetupScreen onSaved={(next) => { writeKioskSetup(next); setSetup(next); }} />;
  }

  return <KioskSession locationId={setup.locationId} sectionId={setup.sectionId} />;
}

function KioskSetupScreen({ onSaved }: { onSaved: (setup: KioskSetup) => void }) {
  const locationsQuery = useQuery({ queryKey: ["kiosk-setup-locations"], queryFn: listLocations });
  const sectionsQuery = useQuery({ queryKey: ["kiosk-setup-sections"], queryFn: listSections });
  const [locationId, setLocationId] = useState("");
  const [sectionId, setSectionId] = useState("");

  const nonSeatingSections = (sectionsQuery.data ?? []).filter((s) => !s.is_seating && s.is_active);

  if (locationsQuery.isLoading || sectionsQuery.isLoading) {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }

  return (
    <div className="relative flex h-dvh w-screen flex-col items-center justify-center bg-background p-6 text-foreground">
      <div className="absolute right-3 top-3">
        <UserMenu />
      </div>
      <img src={logoMark} alt="" className="mb-4 h-12 w-12 object-contain" />
      <h1 className="mb-1 text-lg font-extrabold">Set up this kiosk</h1>
      <p className="mb-5 max-w-xs text-center text-sm text-ink-faint">
        One-time setup for this screen — pick which branch and counter it orders for.
      </p>
      <form
        className="w-full max-w-xs"
        onSubmit={(e) => {
          e.preventDefault();
          if (locationId && sectionId) onSaved({ locationId, sectionId });
        }}
      >
        <label className="mb-1 block text-xs font-bold text-ink-faint">Branch</label>
        <select
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
          className="mb-3 w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-sm outline-none"
        >
          <option value="">Choose a branch…</option>
          {(locationsQuery.data ?? []).map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.name}
            </option>
          ))}
        </select>
        <label className="mb-1 block text-xs font-bold text-ink-faint">Counter / section</label>
        <select
          value={sectionId}
          onChange={(e) => setSectionId(e.target.value)}
          className="mb-4 w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-sm outline-none"
        >
          <option value="">Choose a section…</option>
          {nonSeatingSections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name_en}
            </option>
          ))}
        </select>
        {nonSeatingSections.length === 0 && (
          <p className="mb-3 text-xs font-semibold text-chili">
            No Takeaway-style section found — create one first in Seating Sections (Admin).
          </p>
        )}
        <button
          type="submit"
          disabled={!locationId || !sectionId}
          className="w-full rounded-lg bg-accent py-3 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
        >
          Save and start
        </button>
      </form>
    </div>
  );
}

// Shown before the first order and again after every reset (production request: a
// "fancy" idle screen with a big "Order Here" button rather than jumping straight to
// the menu) — the kiosk session itself is already minted in the background by the time
// this renders (KioskOrderFlow starts it unconditionally), so tapping through has no
// extra latency. `welcomeImageUrl` is this location's Settings upload (Hotel Master);
// null falls back to a built-in gradient + logo + hotel name design rather than a
// blank screen.
function KioskIdleScreen({
  hotelName,
  welcomeImageUrl,
  onStart,
}: {
  hotelName: string | undefined;
  welcomeImageUrl: string | null | undefined;
  onStart: () => void;
}) {
  return (
    <div className="relative flex h-dvh w-screen flex-col items-center justify-center overflow-hidden bg-background text-foreground">
      <div className="absolute right-3 top-3 z-10">
        <UserMenu />
      </div>
      {welcomeImageUrl ? (
        <img src={welcomeImageUrl} alt="" className="absolute inset-0 h-full w-full object-cover" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-accent via-gold to-chili" />
      )}
      <div className="relative z-[1] flex flex-col items-center gap-3 rounded-3xl bg-background/90 px-10 py-12 text-center shadow-pos backdrop-blur-sm">
        <img src={logoMark} alt="" className="h-16 w-16 object-contain" />
        {hotelName && <h1 className="text-2xl font-extrabold">{hotelName}</h1>}
        {!welcomeImageUrl && <p className="text-4xl">🍽️ 🍛 🥤 🍜</p>}
        <button
          type="button"
          onClick={onStart}
          className="mt-3 rounded-full bg-accent px-12 py-4 text-xl font-extrabold text-accent-foreground shadow-pos"
        >
          Order Here
        </button>
      </div>
    </div>
  );
}

// Remounted with a new `epoch` to start a fresh order for the next customer — plain
// state reset, not a page reload, so the kiosk never shows a browser chrome flash.
function KioskSession({ locationId, sectionId }: { locationId: string; sectionId: string }) {
  const [epoch, setEpoch] = useState(0);
  return (
    <KioskOrderFlow
      key={epoch}
      epoch={epoch}
      locationId={locationId}
      sectionId={sectionId}
      onDone={() => setEpoch((e) => e + 1)}
    />
  );
}

function KioskOrderFlow({
  epoch,
  locationId,
  sectionId,
  onDone,
}: {
  epoch: number;
  locationId: string;
  sectionId: string;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [started, setStarted] = useState(false);
  const [tab, setTab] = useState<Tab>("menu");
  const [order, setOrder] = useState<Order | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [profileRequired, setProfileRequired] = useState(false);
  const [pendingPayment, setPendingPayment] = useState<"online" | "cash" | null>(null);
  // Set once a Kiosk cash order's bill finalizes immediately (production request) —
  // shown instead of the Bill tab, then auto-resets like a successful online payment.
  const [cashPaidInfo, setCashPaidInfo] = useState<{ billNumber: string | null; grandTotal: number | null } | null>(
    null,
  );
  // Set the instant an online payment is confirmed. Captured once, straight from the
  // payment-status response, and never refreshed from the guest session again — the
  // guest session closes the moment the kiosk-online bill auto-finalizes, so any
  // further call against it (a bill-preview refetch, a stray window-focus refetch…)
  // would just 404 and bounce this screen to "session ended" instead of the receipt.
  const [onlinePaidInfo, setOnlinePaidInfo] = useState<{ amount: number | null; reference: string | null } | null>(
    null,
  );
  const autoResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scheduleAutoReset() {
    autoResetTimer.current = setTimeout(onDone, AUTO_RESET_MS);
  }

  // The receipt screen's own "Done" button — lets an engaged customer move on right
  // away instead of waiting out the auto-reset countdown.
  function finishNow() {
    if (autoResetTimer.current) clearTimeout(autoResetTimer.current);
    onDone();
  }

  function handleError(err: unknown, fallback: string) {
    if (isSessionEndedError(err)) {
      setSessionEnded(true);
      return;
    }
    setNotice(errorDetail(err) ?? fallback);
  }

  const sessionQuery = useQuery({
    queryKey: ["kiosk-session", locationId, sectionId, epoch],
    queryFn: () => startKioskSession(locationId, sectionId),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  });

  const menuQuery = useQuery({ queryKey: ["guest-menu"], queryFn: getGuestMenu, enabled: sessionQuery.isSuccess });
  const categoriesQuery = useQuery({
    queryKey: ["guest-categories"],
    queryFn: getGuestCategories,
    enabled: sessionQuery.isSuccess,
  });
  const topSellersQuery = useQuery({
    queryKey: ["guest-top-sellers"],
    queryFn: getGuestTopSellers,
    enabled: sessionQuery.isSuccess,
  });
  const [activeCategoryId, setActiveCategoryId] = useState<string>(TOP_SELLING_ID);

  useEffect(() => {
    if (!sessionQuery.isSuccess || !sessionQuery.data.order_id) return;
    void getGuestCart()
      .then(setOrder)
      .catch((err: unknown) => {
        if (isSessionEndedError(err)) setSessionEnded(true);
      });
  }, [sessionQuery.isSuccess, sessionQuery.data?.order_id]);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 3000);
    return () => clearTimeout(t);
  }, [notice]);

  useEffect(() => {
    return () => {
      if (autoResetTimer.current) clearTimeout(autoResetTimer.current);
    };
  }, []);

  async function handleAddItem(item: GuestMenuItem) {
    const current = toLineInputs(order);
    const unsentLine = order?.items.find((l) => l.item_id === item.id && !l.notes && !l.is_kot_sent);
    const next = unsentLine
      ? current.map((l) => (l.id === unsentLine.id ? { ...l, quantity: l.quantity + 1 } : l))
      : [...current, { item_id: item.id, quantity: 1 }];
    try {
      setOrder(await updateGuestCart(next));
    } catch (err) {
      handleError(err, "Couldn't add that item — please try again");
    }
  }

  async function handleQuantityChange(lineId: string, newQty: number) {
    const current = toLineInputs(order);
    const next =
      newQty <= 0
        ? current.filter((l) => l.id !== lineId)
        : current.map((l) => (l.id === lineId ? { ...l, quantity: newQty } : l));
    try {
      setOrder(await updateGuestCart(next));
    } catch (err) {
      handleError(err, "Couldn't update the cart — please try again");
    }
  }

  if (sessionQuery.isLoading) return <CenteredMessage>Loading…</CenteredMessage>;
  if (sessionQuery.isError) {
    return (
      <div className="relative">
        <div className="absolute right-3 top-3">
          <UserMenu />
        </div>
        <CenteredMessage>
          {errorDetail(sessionQuery.error) ?? "Ordering isn't available right now — please ask staff."}
        </CenteredMessage>
      </div>
    );
  }
  if (sessionEnded) {
    return (
      <div className="relative">
        <div className="absolute right-3 top-3">
          <UserMenu />
        </div>
        <CenteredMessage>
          <p className="mb-3">This order timed out.</p>
          <button
            type="button"
            onClick={onDone}
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-extrabold text-accent-foreground"
          >
            Start a new order
          </button>
        </CenteredMessage>
      </div>
    );
  }

  const session = sessionQuery.data as GuestSession;

  if (!started) {
    return (
      <KioskIdleScreen
        hotelName={session.hotel_name}
        welcomeImageUrl={session.kiosk_welcome_image_url}
        onStart={() => setStarted(true)}
      />
    );
  }

  if (profileRequired) {
    return (
      <RequiredProfileScreen
        onSaved={(updated) => {
          queryClient.setQueryData(["kiosk-session", locationId, sectionId, epoch], updated);
          setProfileRequired(false);
          const method = pendingPayment;
          setPendingPayment(null);
          if (method) void handleChoosePayment(method);
        }}
        onSessionEnded={() => {
          setProfileRequired(false);
          setSessionEnded(true);
        }}
        topRight={<UserMenu />}
      />
    );
  }

  if (cashPaidInfo) {
    return (
      <div className="relative">
        <div className="absolute right-3 top-3">
          <UserMenu />
        </div>
        <CenteredMessage>
          <p className="mb-1 text-lg font-extrabold">✅ Paid — thank you!</p>
          <p className="mb-1 text-2xl font-black">{session.pickup_token}</p>
          {cashPaidInfo.billNumber && (
            <p className="mb-4 text-sm text-ink-faint">
              Bill #{cashPaidInfo.billNumber}
              {cashPaidInfo.grandTotal != null ? ` — ${formatINR(cashPaidInfo.grandTotal)}` : ""}
            </p>
          )}
          <button
            type="button"
            onClick={finishNow}
            className="rounded-lg bg-accent px-6 py-3 text-sm font-extrabold text-accent-foreground"
          >
            Done
          </button>
        </CenteredMessage>
      </div>
    );
  }

  if (onlinePaidInfo) {
    return (
      <div className="relative">
        <div className="absolute right-3 top-3">
          <UserMenu />
        </div>
        <CenteredMessage>
          <p className="mb-1 text-lg font-extrabold">✅ Payment received — thank you!</p>
          <p className="mb-1 text-2xl font-black">{session.pickup_token}</p>
          {onlinePaidInfo.amount != null && (
            <p className="mb-4 text-sm text-ink-faint">
              {formatINR(onlinePaidInfo.amount)} paid online
              {onlinePaidInfo.reference ? ` · ${onlinePaidInfo.reference}` : ""}
            </p>
          )}
          <button
            type="button"
            onClick={finishNow}
            className="rounded-lg bg-accent px-6 py-3 text-sm font-extrabold text-accent-foreground"
          >
            Done
          </button>
        </CenteredMessage>
      </div>
    );
  }

  const unsentCount = order?.items.filter((l) => !l.is_kot_sent).length ?? 0;

  async function handleChoosePayment(method: "online" | "cash") {
    if (!session.customer_name || !session.customer_phone) {
      setPendingPayment(method);
      setProfileRequired(true);
      return;
    }
    setBusy(true);
    try {
      const result = await sendGuestOrderToKitchen(method);
      if (result.status === "paid_cash") {
        setCashPaidInfo({ billNumber: result.bill_number ?? null, grandTotal: result.grand_total ?? null });
        scheduleAutoReset();
        return;
      }
      queryClient.setQueryData<GuestSession>(["kiosk-session", locationId, sectionId, epoch], (prev) =>
        prev ? { ...prev, takeaway_payment: method } : prev,
      );
      setOrder(await getGuestCart());
      setCartOpen(false);
      setTab("bill");
    } catch (err) {
      handleError(err, "Couldn't place your order — please try again");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-center gap-2 border-b border-border bg-surface px-4 py-2.5 shadow-pos">
        <img src={logoMark} alt="" className="h-7 w-7 shrink-0 object-contain" />
        <div className="min-w-0 leading-tight">
          <p className="text-base font-black leading-none">{session.pickup_token}</p>
          <p className="text-[11px] font-semibold text-ink-faint">{session.section_name_en} — Self-order kiosk</p>
        </div>
        {/* The Kiosk login's own "log out" — same shared component /pos and /kot use,
            since this screen is standalone (no AppShell sidebar) like those two. */}
        <UserMenu />
      </header>

      {notice && (
        <p className="flex-none border-b border-border bg-accent-soft px-4 py-1.5 text-center text-xs font-semibold text-accent">
          {notice}
        </p>
      )}

      <main className="flex-1 overflow-y-auto">
        {tab === "menu" && (
          <MenuTab
            hotelName={session.hotel_name}
            branchName={session.branch_name}
            items={menuQuery.data ?? []}
            topSellers={topSellersQuery.data ?? []}
            categories={categoriesQuery.data ?? []}
            loading={menuQuery.isLoading}
            activeCategoryId={activeCategoryId}
            onSelectCategory={setActiveCategoryId}
            order={order}
            onAdd={(item) => void handleAddItem(item)}
          />
        )}
        {tab === "status" && (
          <StatusTab takeaway onSessionEnded={() => setSessionEnded(true)} onGoToBill={() => setTab("bill")} />
        )}
        {tab === "bill" && (
          <BillTab
            tokenLabel={session.pickup_token ?? ""}
            paymentMethod={session.takeaway_payment ?? null}
            busy={busy}
            kioskMode
            onChoosePayment={(method) => void handleChoosePayment(method)}
            onSessionEnded={() => setSessionEnded(true)}
            onPaid={(info) => {
              setOnlinePaidInfo(info);
              scheduleAutoReset();
            }}
          />
        )}
      </main>

      <nav className="flex flex-none items-stretch border-t border-border bg-surface">
        {(["menu", "status", "bill"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 text-xs font-extrabold capitalize ${
              tab === t ? "border-t-2 border-accent text-accent" : "text-ink-faint"
            }`}
          >
            {t === "menu" ? "🍽️ Menu" : t === "status" ? "🍳 Status" : "🧾 Pay"}
          </button>
        ))}
      </nav>

      {unsentCount > 0 && tab === "menu" && !cartOpen && (
        <button
          type="button"
          onClick={() => setCartOpen(true)}
          className="fixed bottom-16 right-4 flex items-center gap-2 rounded-full bg-accent px-4 py-3 text-sm font-extrabold text-accent-foreground shadow-pos"
        >
          🛒 {unsentCount} item{unsentCount === 1 ? "" : "s"} · Pay Bill
        </button>
      )}

      {cartOpen && (
        <CartSheet
          order={order}
          busy={busy}
          takeaway
          onQuantityChange={(id, qty) => void handleQuantityChange(id, qty)}
          onSend={() => {}}
          onGoToBill={() => {
            setCartOpen(false);
            setTab("bill");
          }}
          onClose={() => setCartOpen(false)}
        />
      )}
    </div>
  );
}
