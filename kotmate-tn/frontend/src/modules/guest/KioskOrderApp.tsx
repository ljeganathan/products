import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import logoMark from "@/assets/logo-mark.png";
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
  getGuestBillPreview,
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
const AUTO_RESET_MS = 9000;

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
// just without a table/QR to scan and with a few kiosk-only differences: no cash
// option (nobody's there to collect it), a scannable QR instead of an app-intent
// button, and an automatic reset back to a blank cart once an order is paid for.
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

// Remounted with a new `epoch` to start a fresh order for the next customer — plain
// state reset, not a page reload, so the kiosk never shows a browser chrome flash.
function KioskSession({ locationId, sectionId }: { locationId: string; sectionId: string }) {
  const [epoch, setEpoch] = useState(0);
  return (
    <KioskOrderFlow
      key={epoch}
      locationId={locationId}
      sectionId={sectionId}
      onDone={() => setEpoch((e) => e + 1)}
    />
  );
}

function KioskOrderFlow({
  locationId,
  sectionId,
  onDone,
}: {
  locationId: string;
  sectionId: string;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("menu");
  const [order, setOrder] = useState<Order | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);

  function handleError(err: unknown, fallback: string) {
    if (isSessionEndedError(err)) {
      setSessionEnded(true);
      return;
    }
    setNotice(errorDetail(err) ?? fallback);
  }

  const sessionQuery = useQuery({
    queryKey: ["kiosk-session", locationId, sectionId],
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

  const hasUnsentItems = order?.items.some((l) => !l.is_kot_sent) ?? false;
  const onlinePreviewQuery = useQuery({
    queryKey: ["guest-bill-preview"],
    queryFn: getGuestBillPreview,
    enabled: sessionQuery.isSuccess && hasUnsentItems,
  });
  const onlineAvailable = onlinePreviewQuery.data?.online_payment.enabled ?? false;

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

  async function handlePayOnline() {
    setBusy(true);
    try {
      await sendGuestOrderToKitchen("online");
      setOrder(await getGuestCart());
      setCartOpen(false);
      setTab("bill");
    } catch (err) {
      handleError(err, "Couldn't place your order — please try again");
    } finally {
      setBusy(false);
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
  if (!session.customer_name || !session.customer_phone) {
    return (
      <RequiredProfileScreen
        onSaved={(updated) => queryClient.setQueryData(["kiosk-session", locationId, sectionId], updated)}
        onSessionEnded={() => setSessionEnded(true)}
        topRight={<UserMenu />}
      />
    );
  }
  const unsentCount = order?.items.filter((l) => !l.is_kot_sent).length ?? 0;

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
            payAtCounter={false}
            kioskMode
            onSessionEnded={() => setSessionEnded(true)}
            onPaid={() => {
              setTimeout(onDone, AUTO_RESET_MS);
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
          🛒 {unsentCount} item{unsentCount === 1 ? "" : "s"} · Checkout
        </button>
      )}

      {cartOpen && (
        <CartSheet
          order={order}
          busy={busy}
          takeaway
          onlineAvailable={onlineAvailable}
          kioskMode
          onQuantityChange={(id, qty) => void handleQuantityChange(id, qty)}
          onSend={() => void handlePayOnline()}
          onClose={() => setCartOpen(false)}
        />
      )}
    </div>
  );
}
