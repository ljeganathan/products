import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";

import { listCategories } from "@/modules/admin/categoriesApi";
import { listLocations } from "@/modules/admin/locationsApi";
import { listTables } from "@/modules/admin/tablesApi";
import { getMyWaiterProfile, listWaiters } from "@/modules/admin/waitersApi";
import { useAuthStore } from "@/modules/auth/authStore";
import { BillingModal } from "@/modules/pos/BillingModal";
import { CartPanel } from "@/modules/pos/CartPanel";
import { CategoryNav, TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import { ItemCard } from "@/modules/pos/ItemCard";
import { KotTicketsPopup } from "@/modules/pos/KotTicketsPopup";
import { sendOrderToKot } from "@/modules/pos/kotApi";
import {
  type Order,
  type OrderLineInput,
  type PosItem,
  createOrder,
  getOrder,
  listPosItems,
  listPosSections,
  listTopSellers,
  previewOrderUpdate,
  searchItems,
  updateOrder,
} from "@/modules/pos/posApi";
import { RecallPanel } from "@/modules/pos/RecallPanel";
import { SectionChangeConfirm } from "@/modules/pos/SectionChangeConfirm";
import { TableWaiterBar } from "@/modules/pos/TableWaiterBar";
import { usePosWebSocket } from "@/modules/pos/usePosWebSocket";

type SyncState = "idle" | "saving" | "saved" | "error";

function toLineInputs(order: Order | null): OrderLineInput[] {
  if (!order) return [];
  return order.items.map((line) => ({ item_id: line.item_id, quantity: line.quantity, notes: line.notes }));
}

export function POSPage() {
  const role = useAuthStore((s) => s.role)!;
  const queryClient = useQueryClient();

  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const location = locations[0];
  const { data: sections = [] } = useQuery({ queryKey: ["pos-sections"], queryFn: listPosSections });
  const { data: tables = [] } = useQuery({ queryKey: ["pos-tables"], queryFn: listTables });
  const { data: waiters = [] } = useQuery({ queryKey: ["pos-waiters"], queryFn: listWaiters });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const { data: allItems = [] } = useQuery({ queryKey: ["pos-items"], queryFn: () => listPosItems() });
  const { data: topSellers = [] } = useQuery({ queryKey: ["pos-top-sellers"], queryFn: listTopSellers });
  const { data: myWaiterProfile } = useQuery({
    queryKey: ["my-waiter-profile"],
    queryFn: getMyWaiterProfile,
    enabled: role === "waiter",
  });

  const [order, setOrder] = useState<Order | null>(null);
  const [sectionId, setSectionId] = useState<string>("");
  const [tableId, setTableId] = useState<string | null>(null);
  const [waiterId, setWaiterId] = useState<string | null>(null);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncError, setSyncError] = useState<string | null>(null);

  const [activeCategoryId, setActiveCategoryId] = useState<string>(TOP_SELLING_ID);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PosItem[]>([]);
  const [itemCode, setItemCode] = useState("");
  const [itemCodeError, setItemCodeError] = useState<string | null>(null);

  const [openPicker, setOpenPicker] = useState<"table" | "waiter" | null>(null);
  const [showRecall, setShowRecall] = useState(false);
  const [showKotTickets, setShowKotTickets] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [mobileCartOpen, setMobileCartOpen] = useState(false);
  const [kotSending, setKotSending] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [pendingSectionChange, setPendingSectionChange] = useState<{
    sectionId: string;
    tableId: string | null;
    preview: Order;
  } | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const itemCodeInputRef = useRef<HTMLInputElement>(null);

  const stockOverrides = usePosWebSocket(location?.id);

  // Default to the tenant's first active section once loaded, so items can be added
  // before a table is deliberately chosen (common when a cashier starts a walk-in order).
  useEffect(() => {
    if (!sectionId && sections.length > 0) {
      setSectionId(sections[0].id);
    }
  }, [sections, sectionId]);

  useEffect(() => {
    if (role === "waiter") {
      setWaiterId(myWaiterProfile ? myWaiterProfile.id : null);
    }
  }, [role, myWaiterProfile]);

  useEffect(() => {
    if (!searchQuery) {
      setSearchResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      try {
        setSearchResults(await searchItems(searchQuery));
      } catch {
        setSearchResults([]);
      }
    }, 200);
    return () => clearTimeout(timeout);
  }, [searchQuery]);

  const displayedItems = useMemo(() => {
    if (activeCategoryId === TOP_SELLING_ID) return topSellers.filter((i) => i.is_top_seller);
    return allItems.filter((i) => i.category_id === activeCategoryId);
  }, [activeCategoryId, allItems, topSellers]);

  function resolvedPriceFor(item: PosItem): number {
    const line = order?.items.find((l) => l.item_id === item.id);
    return line ? line.unit_price : item.price;
  }

  function quantityInCartFor(item: PosItem): number {
    return order?.items.find((l) => l.item_id === item.id && !l.notes)?.quantity ?? 0;
  }

  async function syncCart(nextItems: OrderLineInput[]) {
    if (!location || !sectionId) return;
    setSyncState("saving");
    setSyncError(null);
    try {
      const result = order
        ? await updateOrder(order.id, { items: nextItems })
        : await createOrder({
            location_id: location.id,
            section_id: sectionId,
            table_id: tableId,
            waiter_id: waiterId,
            items: nextItems,
          });
      setOrder(result);
      setSyncState("saved");
      void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
    } catch (err) {
      setSyncState("error");
      setSyncError(axios.isAxiosError(err) ? String(err.response?.data?.detail ?? err.message) : "Sync failed");
    }
  }

  function isOutOfStock(item: PosItem): boolean {
    const override = stockOverrides[item.id];
    const qty = override?.available_qty ?? item.available_qty;
    return item.track_inventory && qty !== null && qty <= 0;
  }

  async function handleAddItem(item: PosItem) {
    if (isOutOfStock(item)) return;
    const current = toLineInputs(order);
    const existing = current.find((l) => l.item_id === item.id && !l.notes);
    const next = existing
      ? current.map((l) => (l === existing ? { ...l, quantity: l.quantity + 1 } : l))
      : [...current, { item_id: item.id, quantity: 1 }];
    await syncCart(next);
  }

  async function handleQuantityChange(itemId: string, notes: string | null, newQty: number) {
    const current = toLineInputs(order);
    const next =
      newQty <= 0
        ? current.filter((l) => !(l.item_id === itemId && l.notes === notes))
        : current.map((l) => (l.item_id === itemId && l.notes === notes ? { ...l, quantity: newQty } : l));
    await syncCart(next);
  }

  async function handleItemCodeSubmit() {
    if (!itemCode.trim()) return;
    setItemCodeError(null);
    const match = allItems.find((i) => i.item_code === itemCode.trim());
    if (!match) {
      setItemCodeError("No item found with that code");
      return;
    }
    if (isOutOfStock(match)) {
      setItemCodeError(`${match.name_en} is out of stock`);
      itemCodeInputRef.current?.select();
      return;
    }
    await handleAddItem(match);
    setItemCode("");
    itemCodeInputRef.current?.focus();
  }

  async function loadOrderIntoDraft(orderId: string) {
    const fetched = await getOrder(orderId);
    const resumed = fetched.status === "held" ? await updateOrder(orderId, { status: "open" }) : fetched;
    setOrder(resumed);
    setSectionId(resumed.section_id);
    setTableId(resumed.table_id);
    setWaiterId(resumed.waiter_id);
  }

  async function handleSelectTable(newSectionId: string, newTableId: string | null) {
    if (order && order.items.length > 0 && newSectionId !== order.section_id) {
      const preview = await previewOrderUpdate(order.id, {
        section_id: newSectionId,
        table_id: newTableId,
      });
      if (preview.subtotal_changed) {
        setPendingSectionChange({ sectionId: newSectionId, tableId: newTableId, preview: preview.order });
        return;
      }
    }
    setSectionId(newSectionId);
    setTableId(newTableId);
    if (order) {
      const updated = await updateOrder(order.id, { section_id: newSectionId, table_id: newTableId });
      setOrder(updated);
    }
  }

  async function confirmSectionChange() {
    if (!pendingSectionChange || !order) return;
    const updated = await updateOrder(order.id, {
      section_id: pendingSectionChange.sectionId,
      table_id: pendingSectionChange.tableId,
    });
    setOrder(updated);
    setSectionId(pendingSectionChange.sectionId);
    setTableId(pendingSectionChange.tableId);
    setPendingSectionChange(null);
  }

  async function handleSelectWaiter(newWaiterId: string | null) {
    setWaiterId(newWaiterId);
    if (order) {
      const updated = await updateOrder(order.id, { waiter_id: newWaiterId });
      setOrder(updated);
    }
  }

  async function handleHold() {
    if (!order) return;
    await updateOrder(order.id, { status: "held" });
    setOrder(null);
    setTableId(null);
    // A waiter login stays locked to themself for the next order; anyone else starts
    // the next bill unassigned rather than showing the just-held order's waiter.
    if (!isWaiterRole) setWaiterId(null);
    setActionNotice("Bill held");
  }

  async function handleSendKot() {
    if (!order) return;
    setKotSending(true);
    try {
      const result = await sendOrderToKot(order.id);
      setActionNotice(`Sent to kitchen — ticket ${result.ticket_number}`);
    } catch {
      setActionNotice("Kitchen printing lands in the next phase (KOT/Printing)");
    } finally {
      setKotSending(false);
    }
  }

  function handleBill() {
    if (!order || order.items.length === 0) return;
    setShowBilling(true);
  }

  function handleBillFinalized() {
    setShowBilling(false);
    setOrder(null);
    setTableId(null);
    if (!isWaiterRole) setWaiterId(null);
    setActionNotice("Bill finalized");
    void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
  }

  useEffect(() => {
    if (!actionNotice) return;
    const t = setTimeout(() => setActionNotice(null), 3500);
    return () => clearTimeout(t);
  }, [actionNotice]);

  // Keyboard shortcuts (CLAUDE.md §9/Phase 07): F1 is always Top Selling, F2-F9 the
  // next categories (a practical cap — F-keys can't scale to an arbitrarily long
  // category list), F10 table/section, F11 waiter, Ctrl+K search, Ctrl+H hold,
  // Ctrl+Enter send KOT. The item-code field is the primary keyboard-only add path and
  // handles its own Enter key locally.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "F1") {
        e.preventDefault();
        setActiveCategoryId(TOP_SELLING_ID);
      } else if (/^F[2-9]$/.test(e.key)) {
        e.preventDefault();
        const index = Number(e.key.slice(1)) - 2;
        if (categories[index]) setActiveCategoryId(categories[index].id);
      } else if (e.key === "F10") {
        e.preventDefault();
        setOpenPicker("table");
      } else if (e.key === "F11") {
        e.preventDefault();
        if (!isWaiterRole) setOpenPicker("waiter");
      } else if (e.ctrlKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
      } else if (e.ctrlKey && e.key.toLowerCase() === "h") {
        e.preventDefault();
        void handleHold();
      } else if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        void handleSendKot();
      } else if (e.ctrlKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        handleBill();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories, order]);

  const cartItemCount = order?.items.reduce((sum, l) => sum + l.quantity, 0) ?? 0;
  const isWaiterRole = role === "waiter";

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex items-center gap-2.5 border-b border-border bg-surface px-4 py-2 shadow-pos">
        <div className="mr-1 hidden items-center gap-2 border-r border-border pr-3 sm:flex">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-emerald-900 text-[11px] font-extrabold text-accent-foreground">
            KM
          </span>
          <span className="text-[13px] font-extrabold leading-none">POS</span>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <label className="flex min-h-9 flex-1 max-w-[320px] items-center gap-2 rounded-lg border border-border bg-surface-2 px-3">
            <span className="text-xs">🔎</span>
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search items…"
              className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-ink-faint"
            />
            <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 text-[9.5px] font-bold text-ink-faint">
              Ctrl K
            </kbd>
          </label>

          <label className="hidden min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 md:flex">
            <span className="text-xs">#️⃣</span>
            <input
              ref={itemCodeInputRef}
              value={itemCode}
              onChange={(e) => {
                setItemCode(e.target.value);
                setItemCodeError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleItemCodeSubmit();
              }}
              placeholder="Code"
              className="w-14 bg-transparent text-[12.5px] font-bold outline-none placeholder:font-normal placeholder:text-ink-faint"
            />
          </label>
        </div>

        {(role === "pos_user" || role === "tenant_admin") && (
          <button
            type="button"
            onClick={() => setShowKotTickets(true)}
            className="flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
          >
            🍳 KOT Tickets
          </button>
        )}
        <button
          type="button"
          onClick={() => setShowRecall(true)}
          className="flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
        >
          ↺ Recall
        </button>
      </header>

      {itemCodeError && (
        <p className="border-b border-border bg-chili-soft px-4 py-1.5 text-xs font-semibold text-chili">
          {itemCodeError}
        </p>
      )}
      {actionNotice && (
        <p className="border-b border-border bg-accent-soft px-4 py-1.5 text-xs font-semibold text-accent">
          {actionNotice}
        </p>
      )}

      <TableWaiterBar
        sections={sections}
        tables={tables}
        waiters={waiters}
        sectionId={sectionId}
        tableId={tableId}
        waiterId={waiterId}
        waiterLocked={isWaiterRole}
        lockedWaiterName={myWaiterProfile?.name}
        onSelectTable={handleSelectTable}
        onSelectWaiter={handleSelectWaiter}
        openPicker={openPicker}
        onOpenPickerChange={setOpenPicker}
      />

      <div className="flex flex-1 overflow-hidden">
        <CategoryNav
          categories={categories}
          activeCategoryId={activeCategoryId}
          onSelect={setActiveCategoryId}
          variant="rail"
        />

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="lg:hidden">
            <CategoryNav
              categories={categories}
              activeCategoryId={activeCategoryId}
              onSelect={setActiveCategoryId}
              variant="strip"
            />
          </div>

          <div className="flex flex-1 overflow-hidden">
            <div className="grid flex-1 auto-rows-min grid-cols-2 gap-2.5 overflow-y-auto bg-background p-2.5 pb-24 sm:grid-cols-3 md:grid-cols-4 md:pb-2.5 lg:grid-cols-5">
              {(searchQuery ? searchResults : displayedItems).map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  resolvedPrice={resolvedPriceFor(item)}
                  quantityInCart={quantityInCartFor(item)}
                  stockOverride={stockOverrides[item.id]}
                  onAdd={handleAddItem}
                />
              ))}
              {(searchQuery ? searchResults : displayedItems).length === 0 && (
                <p className="col-span-full mt-6 text-center text-sm text-ink-faint">No items found</p>
              )}
            </div>

            <div className="hidden md:flex md:w-80 md:flex-none md:flex-col md:border-l md:border-border lg:w-96">
              <CartPanel
                order={order}
                role={role}
                syncState={syncState}
                onQuantityChange={handleQuantityChange}
                onHold={handleHold}
                onSendKot={handleSendKot}
                onBill={handleBill}
                kotSending={kotSending}
                showSyncIndicator
              />
            </div>
          </div>
        </div>
      </div>

      {syncState === "error" && syncError && (
        <p className="border-t border-border bg-chili-soft px-4 py-1.5 text-xs font-semibold text-chili">
          {syncError}
        </p>
      )}

      {/* Mobile cart FAB + bottom sheet */}
      <button
        type="button"
        onClick={() => setMobileCartOpen(true)}
        className="fixed bottom-5 right-5 z-30 flex min-h-[48px] items-center gap-2 rounded-full bg-accent px-5 text-accent-foreground shadow-pos md:hidden"
      >
        <span className="text-sm font-extrabold">🛒 View Order</span>
        <span className="rounded-full bg-accent-foreground px-2 py-0.5 text-xs font-extrabold text-accent">
          {cartItemCount}
        </span>
      </button>
      {mobileCartOpen && (
        <div className="fixed inset-0 z-50 flex items-end md:hidden">
          <div className="absolute inset-0 bg-black/45" onClick={() => setMobileCartOpen(false)} />
          <div className="relative max-h-[85vh] w-full rounded-t-2xl bg-surface shadow-pos">
            <div className="flex justify-center py-2">
              <span className="h-1.5 w-12 rounded-full bg-surface-3" />
            </div>
            <div className="h-[70vh]">
              <CartPanel
                order={order}
                role={role}
                syncState={syncState}
                onQuantityChange={handleQuantityChange}
                onHold={handleHold}
                onSendKot={handleSendKot}
                onBill={handleBill}
                kotSending={kotSending}
                showSyncIndicator
              />
            </div>
          </div>
        </div>
      )}

      {showRecall && location && (
        <RecallPanel
          locationId={location.id}
          onSelectOrder={async (id) => {
            await loadOrderIntoDraft(id);
            setShowRecall(false);
          }}
          onClose={() => setShowRecall(false)}
        />
      )}
      {showKotTickets && (
        <KotTicketsPopup
          onSelectOrder={async (id) => {
            await loadOrderIntoDraft(id);
            setShowKotTickets(false);
          }}
          onClose={() => setShowKotTickets(false)}
        />
      )}
      {showBilling && order && (
        <BillingModal
          order={order}
          initialPaymentMethod="upi"
          onClose={() => setShowBilling(false)}
          onFinalized={handleBillFinalized}
        />
      )}
      {pendingSectionChange && order && (
        <SectionChangeConfirm
          currentSubtotal={order.subtotal}
          preview={pendingSectionChange.preview}
          onConfirm={confirmSectionChange}
          onCancel={() => setPendingSectionChange(null)}
        />
      )}
    </div>
  );
}
