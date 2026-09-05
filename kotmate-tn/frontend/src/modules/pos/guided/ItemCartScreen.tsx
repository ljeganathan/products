import { useEffect, useState } from "react";

import { formatINR } from "@/lib/utils";
import { CartPanel } from "@/modules/pos/CartPanel";
import { ALL_ITEMS_ID, CategoryNav, TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import { CustomerSelectorBar } from "@/modules/pos/CustomerSelectorBar";
import { ItemCard } from "@/modules/pos/ItemCard";
import { type PosItem, searchItems } from "@/modules/pos/posApi";
import type { TableSelection } from "@/modules/pos/TableWaiterBar";
import type { PosDraftOrder } from "@/modules/pos/usePosDraftOrder";

interface ItemCartScreenProps {
  draft: PosDraftOrder;
  onBack: () => void;
  onSelectCustomer: (selection: TableSelection) => void;
  onOpenBilling: (mode: "bill" | "kot-and-bill") => void;
}

// Item+Cart: Back button + Customer selector (dine-in only) + the existing
// ItemCard/CategoryNav grid + CartPanel — same responsive breakpoints as Default
// layout, search kept, no item-code field/hotkeys (round-1 feedback). Cart action
// labels/behavior branch on order type: dine-in shows "Add to KOT"/"Bill" (fires
// immediately / opens the payment modal); non-seating shows "KOT + Print Bill" /
// "Bill Only (No KOT)" (both open the payment modal — the combined action still needs
// a payment split, it's not a silent fire-and-forget).
export function ItemCartScreen({ draft, onBack, onSelectCustomer, onOpenBilling }: ItemCartScreenProps) {
  const {
    meData,
    role,
    order,
    sectionId,
    sections,
    tableId,
    tables,
    openOrders,
    partyLabel,
    waiterId,
    waiters,
    syncState,
    kotSending,
    categories,
    allItems,
    topSellers,
    stockOverrides,
    resolvedPriceFor,
    quantityInCartFor,
    handleAddItem,
    handleQuantityChange,
    handleSendKot,
    handleClearCart,
    handleHold,
  } = draft;

  const [activeCategoryId, setActiveCategoryId] = useState<string>(TOP_SELLING_ID);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PosItem[]>([]);

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

  const isNonSeating = tableId === null;
  const currentTable = tables.find((t) => t.id === tableId) ?? null;
  const currentWaiter = waiters.find((w) => w.id === waiterId);
  // order.section_name_en is only known once the first item creates the order —
  // before that, fall back to the section already picked on the Order Type screen so
  // the place badge never shows a bare "—" for a freshly-entered non-seating order.
  const currentSection = sections.find((s) => s.id === sectionId);
  const placeLabel = currentTable?.table_number ?? order?.section_name_en ?? currentSection?.name_en ?? "—";
  const kdsEnabled = meData?.features?.kds === true;

  const displayedItems =
    activeCategoryId === TOP_SELLING_ID
      ? topSellers
      : activeCategoryId === ALL_ITEMS_ID
        ? allItems
        : allItems.filter((i) => i.category_id === activeCategoryId);
  const visibleItems = searchQuery ? searchResults : displayedItems;

  async function handleSelectSearchResult(item: PosItem) {
    await handleAddItem(item);
    setSearchQuery("");
  }

  function handleSendKotClick() {
    if (isNonSeating) onOpenBilling("kot-and-bill");
    else void handleSendKot();
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* One bar only — Back, then Table/Customer/Waiter (table/waiter read-only,
          already chosen; only the customer slot stays interactive), then Search
          pushed to the far right. Production feedback: no separate third bar, and
          this bar's colors/chip styling match Default layout's own TableWaiterBar
          exactly (bg-surface-2 bar, bordered table chip, gold waiter chip) rather
          than inventing a different look for the same information. */}
      <div className="flex flex-none items-center gap-2 overflow-x-auto border-b border-border bg-surface-2 px-4 py-2">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          title="Back"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground shadow-pos transition-colors hover:brightness-95"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
            <path d="M4 12L11 5V9H20V15H11V19L4 12Z" />
          </svg>
        </button>
        <div className="flex h-9 shrink-0 items-center gap-2 rounded-lg border border-border bg-surface px-3">
          <span>🍽️</span>
          <span className="text-xl font-black leading-none">{placeLabel}</span>
          {currentTable && (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
              {order?.section_name_en}
            </span>
          )}
        </div>
        {!isNonSeating && currentTable && (
          <CustomerSelectorBar
            table={currentTable}
            currentLabel={partyLabel}
            openOrders={openOrders}
            onSelect={onSelectCustomer}
          />
        )}
        {/* Shown for every dine-in order, and for a non-seating order only once a
            waiter has actually been assigned (the "Require waiter selection for Non
            seating" toggle, when on, assigns one before this screen is ever reached —
            when off, non-seating orders have no waiter concept to surface here). */}
        {(!isNonSeating || waiterId) && (
          <span className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-gold bg-gold-soft px-3 text-sm font-bold text-gold">
            🧑‍🍳 {currentWaiter ? currentWaiter.name : "Unassigned"}
          </span>
        )}
        <div className="ml-auto min-w-0 max-w-[280px] flex-1 shrink-0">
          <label className="flex h-9 items-center gap-2 rounded-lg border border-border bg-surface px-3">
            <span className="text-xs">🔎</span>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search items…"
              className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-ink-faint"
            />
          </label>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <CategoryNav
          categories={categories}
          activeCategoryId={activeCategoryId}
          onSelect={setActiveCategoryId}
          variant="rail"
          showTamilNames={meData?.show_tamil_categories !== false}
          showHotkeyHints={false}
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
            {searchQuery ? (
              <div className="flex-1 overflow-y-auto bg-background p-2.5">
                <ul className="flex flex-col gap-1">
                  {searchResults.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => void handleSelectSearchResult(item)}
                        className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left text-sm hover:bg-surface-2"
                      >
                        <span className="min-w-0 flex-1 truncate font-bold">{item.name_en}</span>
                        <span className="shrink-0 text-xs font-extrabold tabular-nums">
                          {formatINR(resolvedPriceFor(item))}
                        </span>
                      </button>
                    </li>
                  ))}
                  {searchResults.length === 0 && (
                    <li className="px-3 py-2 text-sm text-ink-faint">No items found</li>
                  )}
                </ul>
              </div>
            ) : (
              <div className="grid flex-1 auto-rows-min grid-cols-3 gap-2.5 overflow-y-auto bg-background p-2.5 md:grid-cols-4 lg:grid-cols-5">
                {visibleItems.map((item) => (
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
                {visibleItems.length === 0 && (
                  <p className="col-span-full mt-6 text-center text-sm text-ink-faint">No items found</p>
                )}
              </div>
            )}

            <div className="hidden w-80 flex-none flex-col border-l border-border md:flex lg:w-96">
              <CartPanel
                order={order}
                role={role}
                syncState={syncState}
                onQuantityChange={handleQuantityChange}
                onHold={handleHold}
                onSendKot={handleSendKotClick}
                onBill={() => onOpenBilling("bill")}
                onClear={() => void handleClearCart()}
                kotSending={kotSending}
                showSyncIndicator
                kdsEnabled={kdsEnabled}
                kotLabel={isNonSeating ? "KOT + Print Bill" : undefined}
                billLabel={isNonSeating ? (kdsEnabled ? "Bill Only (No KOT)" : undefined) : undefined}
                hideHotkeyHints
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
