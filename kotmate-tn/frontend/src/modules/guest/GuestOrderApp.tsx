import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import logoMark from "@/assets/logo-mark.png";
import { formatINR } from "@/lib/utils";
import type { Category } from "@/modules/admin/categoriesApi";
import { QrCodeImage } from "@/modules/admin/QrCodeImage";
import { OnlinePayCard } from "@/modules/guest/OnlinePayCard";
import { ALL_ITEMS_ID, CategoryNav, TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import { ItemCard } from "@/modules/pos/ItemCard";
import type { Order, OrderLineInput } from "@/modules/pos/posApi";
import {
  type GuestBillPreview,
  type GuestMenuItem,
  type GuestOrderStatusTicket,
  type GuestSession,
  getGuestBillPreview,
  getGuestCart,
  getGuestCategories,
  getGuestMenu,
  getGuestOrderStatus,
  getGuestTopSellers,
  isTakeawaySession,
  sendGuestOrderToKitchen,
  startGuestSession,
  updateGuestCart,
  updateGuestProfile,
} from "@/modules/guest/guestApi";

type Tab = "menu" | "status" | "bill";

function toLineInputs(order: Order | null): OrderLineInput[] {
  if (!order) return [];
  return order.items.map((line) => ({ id: line.id, item_id: line.item_id, quantity: line.quantity, notes: line.notes }));
}

// Every guest mutation used to fail silently on error (no catch at all in some
// places, or a catch with no user-visible feedback in others) — a stale/expired
// session (closed once staff finalizes the bill, or past its few-hour expiry) then
// looked exactly like a frozen UI: taps just did nothing. These two helpers turn any
// failed guest API call into either a clear toast or, for the specific "this session
// doesn't exist anymore" case, a full-screen prompt to rescan rather than a screen
// that keeps silently rejecting every action.
function errorDetail(err: unknown): string | undefined {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail as string | undefined;
  }
  return undefined;
}

function isSessionEndedError(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 404;
}

// A second, deliberately separate client from the staff app (CLAUDE.md — no sidebar,
// no login screen, no ProtectedRoute) — a customer's own phone, reached by scanning a
// QR code. Two kinds of QR, two very different session shapes: a dine-in TABLE's code
// (Phase 25) is shared — everyone who scans it joins the same cart — while a Takeaway
// SECTION's code (Phase 26) is never shared; every scan starts its own independent
// order with its own pickup token, exactly like two strangers queuing at a counter.
// This component never asks the guest (or shows any UI) to pick a location or a
// customer identity — that's fully determined by which QR it is.
export function GuestOrderApp() {
  const { qrToken = "" } = useParams();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("menu");
  const [order, setOrder] = useState<Order | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);

  function handleGuestError(err: unknown, fallback: string) {
    if (isSessionEndedError(err)) {
      setSessionEnded(true);
      return;
    }
    setNotice(errorDetail(err) ?? fallback);
  }

  // This is a "log in", not a "get current state" — it must run exactly once per page
  // load, never again on its own. React Query's defaults (refetchOnWindowFocus,
  // refetchOnReconnect) would otherwise re-invoke startGuestSession every time the
  // guest merely switches back to this tab. For a dine-in table QR that's merely
  // wasteful (create_or_resume_session resumes the same session), but for a Takeaway
  // QR it's a real bug: every scan mints a brand-new, independent order by design, so
  // an unwanted refetch would silently abandon whatever order the guest already had
  // in progress and hand them a fresh, empty one instead.
  const sessionQuery = useQuery({
    queryKey: ["guest-session", qrToken],
    queryFn: () => startGuestSession(qrToken),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  });

  const menuQuery = useQuery({
    queryKey: ["guest-menu"],
    queryFn: getGuestMenu,
    enabled: sessionQuery.isSuccess,
  });
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

  // Takeaway only: whether the "pay online" choice is offered in the cart — the same answer
  // the Bill tab gets. Asked only once there's something in the cart to pay for.
  const hasUnsentItems = order?.items.some((l) => !l.is_kot_sent) ?? false;
  const onlinePreviewQuery = useQuery({
    queryKey: ["guest-bill-preview"],
    queryFn: getGuestBillPreview,
    enabled: sessionQuery.isSuccess && sessionQuery.data?.table_id === null && hasUnsentItems,
  });
  const onlineAvailable = onlinePreviewQuery.data?.online_payment.enabled ?? false;

  // Rehydrates the draft cart on load — without this a guest who added items but
  // hasn't sent them to the kitchen yet would lose sight of their own cart on refresh.
  useEffect(() => {
    if (!sessionQuery.isSuccess) return;
    if (!sessionQuery.data.order_id) return;
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
      const updated = await updateGuestCart(next);
      setOrder(updated);
    } catch (err) {
      handleGuestError(err, "Couldn't add that item — please try again");
    }
  }

  async function handleQuantityChange(lineId: string, newQty: number) {
    const current = toLineInputs(order);
    const next =
      newQty <= 0
        ? current.filter((l) => l.id !== lineId)
        : current.map((l) => (l.id === lineId ? { ...l, quantity: newQty } : l));
    try {
      const updated = await updateGuestCart(next);
      setOrder(updated);
    } catch (err) {
      handleGuestError(err, "Couldn't update the cart — please try again");
    }
  }

  async function handleSendToKitchen(paymentMethod?: "online" | "cash") {
    setBusy(true);
    try {
      const result = await sendGuestOrderToKitchen(paymentMethod);
      if (paymentMethod) {
        // Written straight into the session (not refetched): the session query must never
        // re-run on its own, since that would mint a new takeaway session.
        queryClient.setQueryData<GuestSession>(["guest-session", qrToken], (prev) =>
          prev ? { ...prev, takeaway_payment: paymentMethod } : prev,
        );
      }
      const fresh = await getGuestCart();
      setOrder(fresh);
      setCartOpen(false);
      if (result.status === "awaiting_payment") {
        // Takeaway paying online: no ticket yet. The bill tab takes the payment, and the
        // ticket is created only once the payment is verified.
        setTab("bill");
        setNotice("Pay to place your order — your ticket is created once payment is confirmed.");
        return;
      }
      setTab("status");
      // Takeaway: the ticket_number here is the pickup token. A cash order waits for the
      // counter to confirm it before it reaches the kitchen.
      setNotice(
        session && isTakeawaySession(session)
          ? `Order placed! Your pickup number: ${result.ticket_number}${paymentMethod === "cash" ? " — pay at the counter" : ""}`
          : `Sent to the kitchen — ticket #${result.ticket_number}`,
      );
    } catch (err) {
      handleGuestError(err, "Couldn't place your order — please try again");
    } finally {
      setBusy(false);
    }
  }

  if (sessionQuery.isLoading) {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }

  if (sessionQuery.isError) {
    return (
      <CenteredMessage>
        {errorDetail(sessionQuery.error) ?? "This QR code isn't valid, or ordering isn't available right now."}
      </CenteredMessage>
    );
  }

  if (sessionEnded) {
    return (
      <CenteredMessage>
        <p className="mb-3">This ordering session has ended — please rescan the QR code.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-lg bg-accent px-4 py-2.5 text-sm font-extrabold text-accent-foreground"
        >
          Start over
        </button>
      </CenteredMessage>
    );
  }

  const session = sessionQuery.data as GuestSession;
  if (!session.customer_name || !session.customer_phone) {
    // Name + phone are mandatory before anything else on a QR order (also enforced
    // server-side in guest_service.update_cart).
    return (
      <RequiredProfileScreen
        onSaved={(updated) => queryClient.setQueryData(["guest-session", qrToken], updated)}
        onSessionEnded={() => setSessionEnded(true)}
      />
    );
  }
  const takeaway = isTakeawaySession(session);
  const unsentCount = order?.items.filter((l) => !l.is_kot_sent).length ?? 0;

  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-center gap-2 border-b border-border bg-surface px-4 py-2.5 shadow-pos">
        <img src={logoMark} alt="" className="h-7 w-7 shrink-0 object-contain" />
        <div className="min-w-0 leading-tight">
          {takeaway ? (
            <>
              <p className="text-base font-black leading-none">{session.pickup_token}</p>
              <p className="text-[11px] font-semibold text-ink-faint">
                {session.section_name_en} — your own order
              </p>
            </>
          ) : (
            <>
              <p className="text-base font-black leading-none">Table {session.table_number}</p>
              <p className="text-[11px] font-semibold text-ink-faint">Shared order for this table</p>
            </>
          )}
        </div>
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          className="ml-auto shrink-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px] font-bold text-ink-soft hover:border-accent"
        >
          {session.customer_name}
        </button>
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
          <StatusTab
            takeaway={takeaway}
            onSessionEnded={() => setSessionEnded(true)}
            onGoToBill={() => setTab("bill")}
          />
        )}
        {tab === "bill" && (
          <BillTab
            tokenLabel={takeaway ? (session.pickup_token ?? "") : `Table ${session.table_number}`}
            payAtCounter={takeaway && session.takeaway_payment === "cash"}
            onSessionEnded={() => setSessionEnded(true)}
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
            {t === "menu" ? "🍽️ Menu" : t === "status" ? "🍳 Status" : "🧾 Bill"}
          </button>
        ))}
      </nav>

      {unsentCount > 0 && tab === "menu" && !cartOpen && (
        <button
          type="button"
          onClick={() => setCartOpen(true)}
          className="fixed bottom-16 right-4 flex items-center gap-2 rounded-full bg-accent px-4 py-3 text-sm font-extrabold text-accent-foreground shadow-pos"
        >
          🛒 {unsentCount} item{unsentCount === 1 ? "" : "s"} · {takeaway ? "Place order" : "Send to kitchen"}
        </button>
      )}

      {cartOpen && (
        <CartSheet
          order={order}
          busy={busy}
          takeaway={takeaway}
          onlineAvailable={onlineAvailable}
          onQuantityChange={(id, qty) => void handleQuantityChange(id, qty)}
          onSend={(paymentMethod) => void handleSendToKitchen(paymentMethod)}
          onClose={() => setCartOpen(false)}
        />
      )}

      {profileOpen && (
        <ProfileSheet
          initialName={session.customer_name}
          initialPhone={session.customer_phone}
          onSaved={(updated) => {
            queryClient.setQueryData(["guest-session", qrToken], updated);
            setProfileOpen(false);
          }}
          onSessionEnded={() => {
            setProfileOpen(false);
            setSessionEnded(true);
          }}
          onClose={() => setProfileOpen(false)}
        />
      )}
    </div>
  );
}

function RequiredProfileScreen({
  onSaved,
  onSessionEnded,
}: {
  onSaved: (updated: GuestSession) => void;
  onSessionEnded: () => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canContinue = name.trim().length > 0 && phone.replace(/\D/g, "").length >= 10;

  async function handleContinue() {
    if (!canContinue) return;
    setSaving(true);
    setError(null);
    try {
      onSaved(await updateGuestProfile({ customer_name: name.trim(), customer_phone: phone.trim() }));
    } catch (err) {
      if (isSessionEndedError(err)) {
        onSessionEnded();
        return;
      }
      setError(errorDetail(err) ?? "Couldn't save — please check your phone number and try again");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex h-dvh w-screen flex-col items-center justify-center bg-background p-6 text-foreground">
      <img src={logoMark} alt="" className="mb-4 h-12 w-12 object-contain" />
      <h1 className="mb-1 text-lg font-extrabold">Welcome!</h1>
      <p className="mb-5 max-w-xs text-center text-sm text-ink-faint">
        Please enter your name and phone number to start ordering.
      </p>
      <form
        className="w-full max-w-xs"
        onSubmit={(e) => {
          e.preventDefault();
          void handleContinue();
        }}
      >
        <input
          autoFocus
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          className="mb-2.5 w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-sm outline-none focus:border-accent"
        />
        <input
          value={phone}
          type="tel"
          maxLength={20}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone number"
          className="mb-3 w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-sm outline-none focus:border-accent"
        />
        {error && <p className="mb-3 text-xs font-semibold text-chili">{error}</p>}
        <button
          type="submit"
          disabled={!canContinue || saving}
          className="w-full rounded-lg bg-accent py-3 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
        >
          {saving ? "Saving…" : "Continue to Menu"}
        </button>
      </form>
    </div>
  );
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh w-screen items-center justify-center bg-background p-6 text-center text-foreground">
      <div className="text-sm font-semibold text-ink-soft">{children}</div>
    </div>
  );
}

function MenuTab({
  hotelName,
  branchName,
  items,
  topSellers,
  categories,
  loading,
  activeCategoryId,
  onSelectCategory,
  order,
  onAdd,
}: {
  hotelName: string;
  branchName: string;
  items: GuestMenuItem[];
  topSellers: GuestMenuItem[];
  categories: Category[];
  loading: boolean;
  activeCategoryId: string;
  onSelectCategory: (categoryId: string) => void;
  order: Order | null;
  onAdd: (item: GuestMenuItem) => void;
}) {
  function quantityInCartFor(item: GuestMenuItem): number {
    return (
      order?.items
        .filter((l) => l.item_id === item.id && !l.notes)
        .reduce((sum, l) => sum + l.quantity, 0) ?? 0
    );
  }

  if (loading) return <p className="p-4 text-sm text-ink-faint">Loading menu…</p>;

  // Same grouping/tabs the staff POS grid already uses (CategoryNav always renders a
  // "Top Selling" and an "All" entry alongside the tenant's real categories).
  const visibleItems =
    activeCategoryId === TOP_SELLING_ID
      ? topSellers
      : activeCategoryId === ALL_ITEMS_ID
        ? items
        : items.filter((i) => i.category_id === activeCategoryId);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-none border-b border-border bg-surface px-4 py-2 text-center">
        <p className="truncate text-sm font-extrabold leading-tight">{hotelName}</p>
        {branchName !== hotelName && (
          <p className="truncate text-[11px] font-semibold text-ink-faint">{branchName}</p>
        )}
      </div>
      <CategoryNav
        categories={categories}
        activeCategoryId={activeCategoryId}
        onSelect={onSelectCategory}
        variant="strip"
        showHotkeyHints={false}
      />
      <div className="grid grid-cols-2 gap-2.5 overflow-y-auto p-3 sm:grid-cols-3">
        {visibleItems.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            resolvedPrice={item.price}
            quantityInCart={quantityInCartFor(item)}
            stockTrackingEnabled
            onAdd={() => onAdd(item)}
          />
        ))}
        {visibleItems.length === 0 && (
          <p className="col-span-full p-4 text-center text-sm text-ink-faint">No items in this category.</p>
        )}
      </div>
    </div>
  );
}

function CartSheet({
  order,
  busy,
  takeaway,
  onlineAvailable,
  onQuantityChange,
  onSend,
  onClose,
}: {
  order: Order | null;
  busy: boolean;
  takeaway: boolean;
  onlineAvailable: boolean;
  onQuantityChange: (lineId: string, qty: number) => void;
  onSend: (paymentMethod?: "online" | "cash") => void;
  onClose: () => void;
}) {
  const unsent = order?.items.filter((l) => !l.is_kot_sent) ?? [];
  const sent = order?.items.filter((l) => l.is_kot_sent) ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/45" onClick={onClose}>
      <div
        className="max-h-[75vh] w-full overflow-y-auto rounded-t-2xl bg-surface p-4 shadow-pos"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-lg font-extrabold">🛒 Your Order</h2>
        {unsent.length === 0 && sent.length === 0 && <p className="text-sm text-ink-faint">Cart is empty.</p>}

        {unsent.length > 0 && (
          <ul className="mb-3 flex flex-col gap-2">
            {unsent.map((line) => (
              <li key={line.id} className="flex items-center justify-between gap-2 rounded-lg bg-surface-2 px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold">{line.name_en}</p>
                  <p className="text-xs text-ink-faint">{formatINR(line.unit_price)} each</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onQuantityChange(line.id!, line.quantity - 1)}
                    className="h-7 w-7 rounded-full bg-surface-3 text-sm font-bold"
                  >
                    −
                  </button>
                  <span className="w-5 text-center text-sm font-bold">{line.quantity}</span>
                  <button
                    type="button"
                    onClick={() => onQuantityChange(line.id!, line.quantity + 1)}
                    className="h-7 w-7 rounded-full bg-surface-3 text-sm font-bold"
                  >
                    +
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {sent.length > 0 && (
          <div className="mb-3">
            <p className="mb-1 text-[11px] font-extrabold uppercase tracking-wide text-ink-faint">
              Already sent to kitchen
            </p>
            <ul className="flex flex-col gap-1">
              {sent.map((line) => (
                <li key={line.id} className="flex items-center justify-between text-xs text-ink-faint">
                  <span>{line.name_en}</span>
                  <span>×{line.quantity}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {takeaway ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-extrabold">How would you like to pay?</p>
            {onlineAvailable && (
              <button
                type="button"
                onClick={() => onSend("online")}
                disabled={unsent.length === 0 || busy}
                className="rounded-lg bg-accent py-3 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
              >
                💳 Pay online now
              </button>
            )}
            <button
              type="button"
              onClick={() => onSend("cash")}
              disabled={unsent.length === 0 || busy}
              className={`rounded-lg py-3 text-sm font-extrabold disabled:opacity-40 ${
                onlineAvailable ? "border border-border hover:bg-surface-2" : "bg-accent text-accent-foreground"
              }`}
            >
              {busy ? "Placing…" : "💵 Pay by cash at the counter"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg py-2 text-sm font-bold text-ink-faint hover:bg-surface-2"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-surface-2"
            >
              Close
            </button>
            <button
              type="button"
              onClick={() => onSend()}
              disabled={unsent.length === 0 || busy}
              className="flex-1 rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
            >
              {busy ? "Placing…" : "Send to Kitchen"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ProfileSheet({
  initialName,
  initialPhone,
  onSaved,
  onSessionEnded,
  onClose,
}: {
  initialName: string | null;
  initialPhone: string | null;
  onSaved: (updated: GuestSession) => void;
  onSessionEnded: () => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(initialName ?? "");
  const [phone, setPhone] = useState(initialPhone ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateGuestProfile({
        customer_name: name || undefined,
        customer_phone: phone || undefined,
      });
      onSaved(updated);
    } catch (err) {
      if (isSessionEndedError(err)) {
        onSessionEnded();
        return;
      }
      // Stays open on failure — closing here (the original bug report) hid the fact
      // that nothing was actually saved, with no way to tell why or retry.
      setError(errorDetail(err) ?? "Couldn't save — please try again");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" onClick={onClose}>
      <div className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-pos" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-lg font-extrabold">Your details</h2>
        <p className="mb-3 text-xs text-ink-faint">Shown on your bill. Update anytime.</p>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          className="mb-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone number"
          className="mb-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none"
        />
        {error && <p className="mb-3 text-xs font-semibold text-chili">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-surface-2"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="flex-1 rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusTab({
  takeaway,
  onSessionEnded,
  onGoToBill,
}: {
  takeaway: boolean;
  onSessionEnded: () => void;
  onGoToBill: () => void;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["guest-order-status"],
    queryFn: getGuestOrderStatus,
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (isSessionEndedError(error)) onSessionEnded();
  }, [error, onSessionEnded]);

  if (isLoading) return <p className="p-4 text-sm text-ink-faint">Loading…</p>;
  const tickets = data ?? [];

  return (
    <div className="flex flex-col gap-2.5 p-3">
      <button
        type="button"
        onClick={onGoToBill}
        className="rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground"
      >
        {takeaway ? "🧾 Bill" : "💳 Pay Bill"}
      </button>
      {tickets.length === 0 && (
        <p className="p-4 text-center text-sm text-ink-faint">
          Nothing sent to the kitchen yet — add items from the Menu tab.
        </p>
      )}
      {tickets.map((ticket: GuestOrderStatusTicket) => (
        <div key={ticket.id} className="rounded-xl border border-border bg-surface p-3.5 shadow-pos">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-2xl font-black leading-none">#{ticket.ticket_number}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-extrabold capitalize ${
                ticket.status === "ready"
                  ? "bg-veg/15 text-veg"
                  : ticket.status === "preparing"
                    ? "bg-gold-soft text-gold"
                    : "bg-surface-3 text-ink-soft"
              }`}
            >
              {ticket.status}
            </span>
          </div>
          <ul className="flex flex-col gap-1">
            {ticket.items.map((item, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span>
                  {item.name_en}
                  {item.name_ta && <span className="ml-1.5 text-xs text-ink-faint">{item.name_ta}</span>}
                </span>
                <span className="font-bold">×{item.quantity}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function BillTab({
  tokenLabel,
  payAtCounter,
  onSessionEnded,
}: {
  tokenLabel: string;
  payAtCounter: boolean;
  onSessionEnded: () => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery<GuestBillPreview>({
    queryKey: ["guest-bill-preview"],
    queryFn: getGuestBillPreview,
    retry: false,
  });

  useEffect(() => {
    if (isSessionEndedError(error)) onSessionEnded();
  }, [error, onSessionEnded]);

  if (isLoading) return <p className="p-4 text-sm text-ink-faint">Loading…</p>;
  if (isError || !data) {
    return <p className="p-4 text-center text-sm text-ink-faint">Add items to see your bill here.</p>;
  }

  return (
    <div className="p-4">
      <div className="rounded-xl border border-border bg-surface p-4 shadow-pos">
        <h2 className="mb-3 text-sm font-extrabold uppercase tracking-wide text-ink-faint">Your Bill</h2>
        <ul className="mb-3 flex flex-col gap-1.5">
          {data.items.map((item) => (
            <li key={item.item_id} className="flex items-center justify-between text-sm">
              <span>
                {item.name_en} <span className="text-ink-faint">×{item.quantity}</span>
              </span>
              <span className="font-bold tabular-nums">{formatINR(item.line_total)}</span>
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-1 border-t border-dashed border-border pt-2 text-sm">
          <Row label="Subtotal" value={data.subtotal} />
          {data.discount_amount > 0 && <Row label={data.discount_note ?? "Discount"} value={-data.discount_amount} />}
          <Row label="CGST" value={data.cgst_amount} />
          <Row label="SGST" value={data.sgst_amount} />
          {data.round_off_amount !== 0 && <Row label="Round Off" value={data.round_off_amount} />}
          <div className="mt-1 flex items-center justify-between border-t border-border pt-2 text-base font-extrabold">
            <span>Total</span>
            <span className="tabular-nums">{formatINR(data.grand_total)}</span>
          </div>
        </div>
      </div>

      {payAtCounter && (
        <div className="mt-4 rounded-xl border border-border bg-surface p-4 text-center shadow-pos">
          <p className="text-sm font-extrabold">💵 Pay at the counter</p>
          <p className="mt-1 text-xs text-ink-faint">Pay when you collect your order, with the pickup number above.</p>
        </div>
      )}

      {!payAtCounter && data.online_payment.enabled && (
        <OnlinePayCard
          info={data.online_payment}
          total={data.grand_total}
          tokenLabel={tokenLabel}
          onPaid={() => void queryClient.invalidateQueries({ queryKey: ["guest-bill-preview"] })}
          onSessionEnded={onSessionEnded}
        />
      )}

      {!payAtCounter && !data.online_payment.enabled && data.upi_link && (
        <div className="mt-4 rounded-xl border border-border bg-surface p-4 text-center shadow-pos">
          <h2 className="mb-1 text-sm font-extrabold uppercase tracking-wide text-ink-faint">
            💳 Scan to Pay via UPI
          </h2>
          <p className="mb-1 text-xs text-ink-faint">Scan with any UPI app, or download and pay from another device.</p>
          <QrCodeImage value={data.upi_link} downloadName={`upi-payment-${Math.round(data.grand_total)}`} />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between text-ink-soft">
      <span>{label}</span>
      <span className="tabular-nums">{formatINR(value)}</span>
    </div>
  );
}
