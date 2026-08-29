import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import logoMark from "@/assets/logo-mark.png";
import { formatINR } from "@/lib/utils";
import { UserMenu } from "@/modules/auth/UserMenu";
import { BillingModal } from "@/modules/pos/BillingModal";
import { CartPanel } from "@/modules/pos/CartPanel";
import { ALL_ITEMS_ID, CategoryNav, TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import { FastBillingModal } from "@/modules/pos/FastBillingModal";
import { ItemCard } from "@/modules/pos/ItemCard";
import { ItemCodeModal } from "@/modules/pos/ItemCodeModal";
import { KotTicketsPopup } from "@/modules/pos/KotTicketsPopup";
import { type PosItem, searchItems } from "@/modules/pos/posApi";
import { RecallPanel } from "@/modules/pos/RecallPanel";
import { SectionChangeConfirm } from "@/modules/pos/SectionChangeConfirm";
import { TableWaiterBar } from "@/modules/pos/TableWaiterBar";
import { usePosDraftOrder } from "@/modules/pos/usePosDraftOrder";

export function POSPage() {
  const {
    role,
    isWaiterRole,
    queryClient,
    meData,
    locations,
    location,
    handleLocationChange,
    sections,
    tables,
    waiters,
    categories,
    allItems,
    topSellers,
    myWaiterProfile,
    openOrders,
    order,
    sectionId,
    tableId,
    partyLabel,
    waiterId,
    syncState,
    syncError,
    readyToOrder,
    waiterMandatory,
    missingSelectionMessage,
    actionNotice,
    setActionNotice,
    kotSending,
    pendingSectionChange,
    setPendingSectionChange,
    resolvedPriceFor,
    quantityInCartFor,
    stockOverrides,
    handleAddItem,
    handleQuantityChange,
    resolveAndAddItemByCode,
    loadOrderIntoDraft,
    handleSelectTable,
    handleSelectWaiter,
    confirmSectionChange,
    handleClearCart,
    handleHold,
    handleSendKot,
    resetDraft,
    dropOrderFromOpenOrdersCache,
  } = usePosDraftOrder();

  const [activeCategoryId, setActiveCategoryId] = useState<string>(TOP_SELLING_ID);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PosItem[]>([]);
  const [searchHighlight, setSearchHighlight] = useState(0);
  const [itemCode, setItemCode] = useState("");
  const [itemCodeError, setItemCodeError] = useState<string | null>(null);

  const [openPicker, setOpenPicker] = useState<"table" | "waiter" | null>(null);
  const [showRecall, setShowRecall] = useState(false);
  const [showItemCodeModal, setShowItemCodeModal] = useState(false);
  const [showFastBilling, setShowFastBilling] = useState(false);
  const [showKotTickets, setShowKotTickets] = useState(false);
  const [billingMode, setBillingMode] = useState<"bill" | "kot-and-bill" | null>(null);
  const [mobileCartOpen, setMobileCartOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchWrapperRef = useRef<HTMLDivElement>(null);
  const itemCodeInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setSearchHighlight(0);
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

  // Click-outside closes the results dropdown (visibility is just searchQuery-driven,
  // so "closing" here means clearing the query — Esc already does the same via the
  // window-level handler below).
  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (searchQuery && !searchWrapperRef.current?.contains(e.target as Node)) {
        setSearchQuery("");
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [searchQuery]);

  const displayedItems = useMemo(() => {
    // `topSellers` is already the resolved list (manually pinned items first, backfilled
    // with recent best-sellers server-side, POS-31) — re-filtering to is_top_seller here
    // would silently drop every dynamically-computed item.
    if (activeCategoryId === TOP_SELLING_ID) return topSellers;
    if (activeCategoryId === ALL_ITEMS_ID) return allItems;
    return allItems.filter((i) => i.category_id === activeCategoryId);
  }, [activeCategoryId, allItems, topSellers]);

  async function handleSelectSearchResult(item: PosItem) {
    await handleAddItem(item);
    setSearchQuery("");
    searchInputRef.current?.focus();
  }

  // Shared by the header's inline Code field, ItemCodeModal (mobile/tablet-narrow), and
  // FastBillingModal's Item slot — one place that does the actual lookup + stock check +
  // cart-add, so all three entry points behave identically.
  async function handleItemCodeSubmit(onDone?: (success: boolean) => void) {
    const code = itemCode.trim();
    if (!code) return;
    if (!readyToOrder) {
      setActionNotice(missingSelectionMessage);
      setOpenPicker(!sectionId ? "table" : "waiter");
      return;
    }
    setItemCodeError(null);
    const result = await resolveAndAddItemByCode(code);
    if (!result.ok) {
      setItemCodeError(result.error);
      onDone?.(false);
      return;
    }
    setItemCode("");
    onDone?.(true);
  }

  const isNonSeating = tableId === null;
  const kdsEnabled = meData?.features?.kds === true;

  function handleBill() {
    if (!order || order.items.length === 0) return;
    setBillingMode("bill");
  }

  // Non-seating orders (Takeaway/Online Delivery) fire the kitchen ticket and finalize
  // the bill in the same action, same as Guided POS's ItemCartScreen — a takeaway
  // customer pays before the food is handed over (CLAUDE.md §11), so a separate
  // "Add to KOT" step here would just be an extra click for no reason.
  function handleSendKotClick() {
    if (isNonSeating) setBillingMode("kot-and-bill");
    else void handleSendKot();
  }

  function handleBillFinalized(printWarning?: string) {
    const billedOrderId = order?.id;
    if (billedOrderId) dropOrderFromOpenOrdersCache(billedOrderId);
    setBillingMode(null);
    resetDraft();
    setActionNotice(printWarning ? `Bill finalized — ${printWarning}` : "Bill finalized");
    void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
  }

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
        handleSendKotClick();
      } else if (e.ctrlKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        handleBill();
      } else if (e.key === "Escape") {
        // A search/item-code field mid-edit clears itself first — a bare Esc when
        // nothing's focused there clears the whole draft cart (CLAUDE.md §9, POS-23).
        if (searchQuery) {
          setSearchQuery("");
        } else if (itemCode) {
          setItemCode("");
        } else {
          e.preventDefault();
          void handleClearCart();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories, order, searchQuery, itemCode]);

  const cartItemCount = order?.items.reduce((sum, l) => sum + l.quantity, 0) ?? 0;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex items-center gap-2.5 border-b border-border bg-surface px-4 py-2 shadow-pos">
        <div className="mr-1 hidden items-center gap-2 border-r border-border pr-3 sm:flex">
          <img src={logoMark} alt="KOTMate TN" className="h-7 w-7 object-contain" />
          <div className="leading-tight">
            <p className="truncate text-base font-extrabold" title={meData?.company_name ?? undefined}>
              {meData?.company_name ?? "POS"}
            </p>
            {location && locations.length > 1 ? (
              <select
                value={location.id}
                onChange={(e) => handleLocationChange(e.target.value)}
                className="max-w-[160px] truncate rounded border-none bg-transparent p-0 text-xs font-semibold text-ink-faint outline-none"
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </select>
            ) : (
              location && <p className="truncate text-xs font-semibold text-ink-faint">{location.name}</p>
            )}
          </div>
        </div>

        {/* Mobile-width counterpart of the location picker above — that one is inside
            a `hidden sm:flex` branding block, so on a phone it never renders at all,
            leaving no way to tell/change which location a cashier is billing against
            (matters whenever a phone is used as a real billing terminal, not just a
            waiter's order-taking device, e.g. with a printer attached — CLAUDE.md §9).
            `sm:hidden` keeps exactly one of the two pickers visible at any width. */}
        {location && locations.length > 1 && (
          <select
            value={location.id}
            onChange={(e) => handleLocationChange(e.target.value)}
            className="min-h-9 max-w-[110px] shrink-0 truncate rounded-lg border border-border bg-surface-2 px-2 text-xs font-semibold text-ink-soft outline-none sm:hidden"
          >
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name}
              </option>
            ))}
          </select>
        )}

        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <div ref={searchWrapperRef} className="relative max-w-[320px] flex-1">
            <label className="flex min-h-9 items-center gap-2 rounded-lg border border-border bg-surface-2 px-3">
              <span className="text-xs">🔎</span>
              <input
                ref={searchInputRef}
                value={searchQuery}
                disabled={!readyToOrder}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (searchResults.length === 0) return;
                  const max = Math.min(searchResults.length, 8) - 1;
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setSearchHighlight((h) => Math.min(h + 1, max));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setSearchHighlight((h) => Math.max(h - 1, 0));
                  } else if (e.key === "Enter") {
                    e.preventDefault();
                    void handleSelectSearchResult(searchResults[searchHighlight]);
                  }
                }}
                placeholder={readyToOrder ? "Search items…" : (missingSelectionMessage ?? "Search items…")}
                className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-ink-faint disabled:cursor-not-allowed"
              />
              <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 text-[9.5px] font-bold text-ink-faint">
                Ctrl K
              </kbd>
            </label>

            {searchQuery && (
              <ul className="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-lg border border-border bg-surface shadow-pos">
                {searchResults.slice(0, 8).map((item, i) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => void handleSelectSearchResult(item)}
                      onMouseEnter={() => setSearchHighlight(i)}
                      className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm ${
                        i === searchHighlight ? "bg-accent-soft text-accent" : "hover:bg-surface-2"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate">
                        <span className="font-bold">{item.name_en}</span>
                        {item.item_code && (
                          <span className="ml-1.5 font-mono text-[10px] text-ink-faint">#{item.item_code}</span>
                        )}
                        {item.name_ta && <span className="ta block text-xs font-medium text-ink-soft">{item.name_ta}</span>}
                      </span>
                      <span className="shrink-0 text-xs font-extrabold tabular-nums">
                        {formatINR(resolvedPriceFor(item))}
                      </span>
                    </button>
                  </li>
                ))}
                {searchResults.length === 0 && (
                  <li className="px-3 py-2 text-xs text-ink-faint">No items found</li>
                )}
              </ul>
            )}
          </div>

          {/* `shrink-0` — without it, this label was the only sibling with give left in
              the search-wrapper's flex row once a real tenant name + multi-location
              picker + long-ish login id pushed the header tight even above `lg`
              (production feedback, tablet-landscape ~1200px CSS width): the search box's
              own `flex-1` claimed space first, and this element being the next item with
              default flex-shrink collapsed its input down to invisible, leaving only the
              icon in a squeezed box — never actually falling back to the "⋮" menu, just
              silently losing its input. */}
          <label className="hidden min-h-9 shrink-0 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 lg:flex">
            <span className="text-xs">#️⃣</span>
            <input
              ref={itemCodeInputRef}
              value={itemCode}
              disabled={!readyToOrder}
              onChange={(e) => {
                setItemCode(e.target.value);
                setItemCodeError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  void handleItemCodeSubmit((success) =>
                    success ? itemCodeInputRef.current?.focus() : itemCodeInputRef.current?.select(),
                  );
                }
              }}
              placeholder="Code"
              className="w-14 bg-transparent text-[12.5px] font-bold outline-none placeholder:font-normal placeholder:text-ink-faint disabled:cursor-not-allowed"
            />
          </label>
        </div>

        {/* KOT Tickets / Recall / Dashboard (+ the inline Code field above) all fit fine
            on a genuinely spacious desktop, but crowd the header into overflow anywhere
            narrower — including tablet-landscape/phone-landscape widths in the 768-
            1024px range, where the item-code entry point was getting clipped off-screen
            with no way to reach it at all (production feedback) after `md` (768px)
            turned out too tight once the Code field joined this same header. `lg`
            (1024px) leaves real margin; below it these collapse into the "⋮" menu instead. */}
        <div className="hidden items-center gap-2.5 lg:flex">
          {(role === "pos_user" || role === "tenant_admin" || role === "pos_operator") &&
            meData?.features?.kds === true && (
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
          {(role === "pos_user" || role === "tenant_admin") && (
            <Link
              to="/dashboard"
              className="flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
            >
              📊 Dashboard
            </Link>
          )}
        </div>

        <div className="relative lg:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen((v) => !v)}
            aria-label="More actions"
            className="flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border bg-surface-2 text-base font-bold text-ink-soft hover:border-accent hover:text-accent"
          >
            ⋮
          </button>
          {mobileMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMobileMenuOpen(false)} />
              <div className="absolute right-0 top-full z-50 mt-1.5 flex w-44 flex-col gap-1 rounded-lg border border-border bg-surface p-1.5 shadow-pos">
                <button
                  type="button"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    if (!readyToOrder) {
                      setActionNotice(missingSelectionMessage);
                      setOpenPicker(!sectionId ? "table" : "waiter");
                    } else {
                      setShowItemCodeModal(true);
                    }
                  }}
                  className="flex min-h-9 items-center gap-2 rounded-md px-2.5 text-left text-xs font-bold text-ink-soft hover:bg-surface-2"
                >
                  #️⃣ Item Code
                </button>
                {(role === "pos_user" || role === "tenant_admin" || role === "pos_operator") &&
                  meData?.features?.kds === true && (
                    <button
                      type="button"
                      onClick={() => {
                        setShowKotTickets(true);
                        setMobileMenuOpen(false);
                      }}
                      className="flex min-h-9 items-center gap-2 rounded-md px-2.5 text-left text-xs font-bold text-ink-soft hover:bg-surface-2"
                    >
                      🍳 KOT Tickets
                    </button>
                  )}
                <button
                  type="button"
                  onClick={() => {
                    setShowRecall(true);
                    setMobileMenuOpen(false);
                  }}
                  className="flex min-h-9 items-center gap-2 rounded-md px-2.5 text-left text-xs font-bold text-ink-soft hover:bg-surface-2"
                >
                  ↺ Recall
                </button>
                {(role === "pos_user" || role === "tenant_admin") && (
                  <Link
                    to="/dashboard"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex min-h-9 items-center gap-2 rounded-md px-2.5 text-xs font-bold text-ink-soft hover:bg-surface-2"
                  >
                    📊 Dashboard
                  </Link>
                )}
              </div>
            </>
          )}
        </div>

        <UserMenu />
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
        openOrders={openOrders}
        sectionId={sectionId}
        tableId={tableId}
        partyLabel={partyLabel}
        waiterId={waiterId}
        waiterLocked={isWaiterRole}
        lockedWaiterName={myWaiterProfile?.name}
        onSelectTable={handleSelectTable}
        onSelectWaiter={handleSelectWaiter}
        openPicker={openPicker}
        onOpenPickerChange={setOpenPicker}
        onOpenFastBilling={() => setShowFastBilling(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        <CategoryNav
          categories={categories}
          activeCategoryId={activeCategoryId}
          onSelect={setActiveCategoryId}
          variant="rail"
          showTamilNames={meData?.show_tamil_categories !== false}
        />

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="lg:hidden">
            <CategoryNav
              categories={categories}
              activeCategoryId={activeCategoryId}
              onSelect={setActiveCategoryId}
              variant="strip"
              showTamilNames={meData?.show_tamil_categories !== false}
            />
          </div>

          <div className="flex flex-1 overflow-hidden">
            {!readyToOrder ? (
              // Table/section (or Takeaway) and waiter are mandatory before an order can
              // start (production feedback) — the item grid itself is the gate, so a tap
              // can never silently no-op the way it did when a section auto-defaulted.
              <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-background p-8 text-center">
                <span className="text-3xl">🍽️</span>
                <p className="max-w-xs text-sm font-semibold text-ink-soft">{missingSelectionMessage}</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {!sectionId && (
                    <button
                      type="button"
                      onClick={() => setOpenPicker("table")}
                      className="rounded-lg border border-accent bg-accent-soft px-4 py-2 text-sm font-extrabold text-accent"
                    >
                      🍽️ Select Table / Takeaway
                    </button>
                  )}
                  {sectionId && !isWaiterRole && !waiterId && (
                    <button
                      type="button"
                      onClick={() => setOpenPicker("waiter")}
                      className="rounded-lg border border-gold bg-gold-soft px-4 py-2 text-sm font-extrabold text-gold"
                    >
                      🧑‍🍳 Assign Waiter
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="grid flex-1 auto-rows-min grid-cols-2 gap-2.5 overflow-y-auto bg-background p-2.5 pb-24 sm:grid-cols-3 md:grid-cols-4 md:pb-2.5 lg:grid-cols-5">
                {(searchQuery ? searchResults : displayedItems).map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    resolvedPrice={resolvedPriceFor(item)}
                    quantityInCart={quantityInCartFor(item)}
                    stockOverride={stockOverrides[item.id]}
                    stockTrackingEnabled={meData?.stock_tracking_enabled === true}
                    onAdd={handleAddItem}
                  />
                ))}
                {(searchQuery ? searchResults : displayedItems).length === 0 && (
                  <p className="col-span-full mt-6 text-center text-sm text-ink-faint">No items found</p>
                )}
              </div>
            )}

            <div className="hidden md:flex md:w-80 md:flex-none md:flex-col md:border-l md:border-border lg:w-96">
              <CartPanel
                order={order}
                role={role}
                syncState={syncState}
                onQuantityChange={handleQuantityChange}
                onHold={handleHold}
                onSendKot={handleSendKotClick}
                onBill={handleBill}
                onClear={() => void handleClearCart()}
                kotSending={kotSending}
                showSyncIndicator
                kdsEnabled={kdsEnabled}
                kotLabel={isNonSeating ? "KOT + Print Bill" : undefined}
                billLabel={isNonSeating ? (kdsEnabled ? "Bill Only (No KOT)" : undefined) : undefined}
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
                onSendKot={handleSendKotClick}
                onBill={handleBill}
                onClear={() => void handleClearCart()}
                kotSending={kotSending}
                showSyncIndicator
                kdsEnabled={kdsEnabled}
                kotLabel={isNonSeating ? "KOT + Print Bill" : undefined}
                billLabel={isNonSeating ? (kdsEnabled ? "Bill Only (No KOT)" : undefined) : undefined}
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
      {billingMode && order && (
        <BillingModal
          order={order}
          initialPaymentMethod={meData?.default_payment_method ?? "cash"}
          mode={billingMode}
          onClose={() => setBillingMode(null)}
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
      {showItemCodeModal && (
        <ItemCodeModal
          itemCode={itemCode}
          onItemCodeChange={(value) => {
            setItemCode(value);
            setItemCodeError(null);
          }}
          itemCodeError={itemCodeError}
          onSubmit={() => void handleItemCodeSubmit()}
          onClose={() => setShowItemCodeModal(false)}
        />
      )}
      {showFastBilling && (
        <FastBillingModal
          tables={tables}
          waiters={waiters}
          sections={sections}
          waiterLocked={isWaiterRole}
          waiterMandatory={waiterMandatory}
          onSelectTable={handleSelectTable}
          onSelectWaiter={handleSelectWaiter}
          onAddItemByCode={resolveAndAddItemByCode}
          onClose={() => setShowFastBilling(false)}
        />
      )}
    </div>
  );
}
