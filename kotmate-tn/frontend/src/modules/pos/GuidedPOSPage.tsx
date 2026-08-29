import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import logoMark from "@/assets/logo-mark.png";
import { UserMenu } from "@/modules/auth/UserMenu";
import { BillingModal } from "@/modules/pos/BillingModal";
import { FastBillingScreen } from "@/modules/pos/guided/FastBillingScreen";
import { type GuidedArea, LeftRail } from "@/modules/pos/guided/LeftRail";
import { ItemCartScreen } from "@/modules/pos/guided/ItemCartScreen";
import { KotTicketsScreen } from "@/modules/pos/guided/KotTicketsScreen";
import { OrderTypeScreen } from "@/modules/pos/guided/OrderTypeScreen";
import { RecallScreen } from "@/modules/pos/guided/RecallScreen";
import { listActiveKotTickets } from "@/modules/pos/kotApi";
import type { PosSection } from "@/modules/pos/posApi";
import { SectionChangeConfirm } from "@/modules/pos/SectionChangeConfirm";
import { resolveCustomerSlotSelection, type TableSelection, WaiterPickerModal } from "@/modules/pos/TableWaiterBar";
import { usePosDraftOrder } from "@/modules/pos/usePosDraftOrder";
import type { Table } from "@/modules/admin/tablesApi";

type BillingSubScreen = "order-type" | "item-cart";

// Guided POS — the Petpooja-style step-by-step alternative to Default layout's
// hotkey-driven counter screen. Owns `activeArea` (Billing/KOT Tickets/Fast Billing,
// left rail) and the Billing area's own `screen` sub-state; every order/table/waiter/
// cart mechanic is delegated to the same usePosDraftOrder hook POSPage.tsx uses, so
// the two layouts can never silently diverge on that subtle, already-tested logic.
export function GuidedPOSPage() {
  const draft = usePosDraftOrder();
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
    openOrders,
    sectionId,
    tableId,
    order,
    waiterId,
    waiterMandatory,
    actionNotice,
    setActionNotice,
    pendingSectionChange,
    confirmSectionChange,
    setPendingSectionChange,
    handleSelectTable,
    handleSelectWaiter,
    loadOrderIntoDraft,
    resetDraft,
    dropOrderFromOpenOrdersCache,
  } = draft;

  const [activeArea, setActiveArea] = useState<GuidedArea>("billing");
  const [screen, setScreen] = useState<BillingSubScreen>("order-type");
  const [pendingWaiterFor, setPendingWaiterFor] = useState<TableSelection | null>(null);
  const [billingMode, setBillingMode] = useState<"bill" | "kot-and-bill" | null>(null);

  const kdsEnabled = meData?.features?.kds === true;
  // The rail is an entry chooser (Order Type / KOT Tickets / Fast Billing) — once a
  // specific order's Item+Cart screen is open, it's replaced by just the Back button
  // so billing gets the full screen width with no competing nav (production feedback).
  const showRail = !(activeArea === "billing" && screen === "item-cart");
  const dashboardAccessible = role === "pos_user" || role === "tenant_admin";

  const { data: activeTickets = [] } = useQuery({
    queryKey: ["kot-tickets-active"],
    queryFn: () => listActiveKotTickets(),
    enabled: kdsEnabled,
    retry: false,
  });
  const openTicketCount = new Set(activeTickets.map((t) => t.order_id)).size;

  // Every draft-reset path (Hold, KOT sent, Bill finalized, Clear with already-sent
  // lines) clears sectionId to "" — one effect handles the Item+Cart → Order Type
  // transition uniformly instead of wrapping each individual handler.
  useEffect(() => {
    if (screen === "item-cart" && !sectionId) {
      setScreen("order-type");
    }
  }, [screen, sectionId]);

  async function selectCustomerSlot(table: Table, label: string) {
    const selection = resolveCustomerSlotSelection(table, label, openOrders);
    await handleSelectTable(selection);
    if (selection.kind === "resume") {
      setScreen("item-cart");
      return;
    }
    // New/empty slot — a waiter already assigned at this table (from a previous
    // customer slot) carries over rather than being cleared (production feedback), so
    // the popup only interrupts when there's genuinely no waiter yet. The tenant's
    // "Require waiter selection" toggle (admin-settings-only, never on the POS screen
    // itself, common to both layouts) gates whether it's mandatory at all.
    if (!isWaiterRole && waiterMandatory && !waiterId) {
      setPendingWaiterFor(selection);
    } else {
      setScreen("item-cart");
    }
  }

  function handleSelectNonSeating(section: PosSection) {
    void handleSelectTable({ kind: "direct", sectionId: section.id, tableId: null });
    setScreen("item-cart");
  }

  async function handleWaiterPicked(waiterId: string) {
    await handleSelectWaiter(waiterId);
    setPendingWaiterFor(null);
    setScreen("item-cart");
  }

  function handleWaiterPopupCancel() {
    resetDraft();
    setPendingWaiterFor(null);
  }

  function handleBillFinalized(printWarning?: string) {
    const billedOrderId = order?.id;
    if (billedOrderId) dropOrderFromOpenOrdersCache(billedOrderId);
    setBillingMode(null);
    resetDraft();
    setActionNotice(printWarning ? `Bill finalized — ${printWarning}` : "Bill finalized");
    void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
    void queryClient.invalidateQueries({ queryKey: ["kot-tickets-active"] });
  }

  async function handleSelectOrderFromList(orderId: string) {
    await loadOrderIntoDraft(orderId);
    setActiveArea("billing");
    setScreen("item-cart");
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      {/* Full window width — the left rail starts only below this row (production
          feedback), not beside it for the full page height. */}
      <div className="flex flex-none items-center gap-2.5 border-b border-border bg-surface px-4 py-2 shadow-pos">
        <img src={logoMark} alt="KOTMate TN" className="h-7 w-7 shrink-0 object-contain" />
        <div className="mr-auto min-w-0 leading-tight">
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
        {/* Home + UserMenu grouped into one shrink-to-fit wrapper so UserMenu's own
            internal `ml-auto` (it's shared with other standalone screens that rely on
            it to self-push right) has no leftover space to consume here — otherwise it
            competes with the `mr-auto` above and strands Home in the middle of the bar
            instead of flush against the user menu. */}
        <div className="flex shrink-0 items-center gap-2.5">
          {/* Hidden entirely (not just disabled) while a specific order's Item+Cart
              screen is open — same "focused billing, no distractions" rule as the left
              rail (production feedback). */}
          {showRail &&
            (dashboardAccessible ? (
              <Link
                to="/dashboard"
                className="flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
              >
                🏠 Home
              </Link>
            ) : (
              <button
                type="button"
                disabled
                className="flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-faint opacity-40"
              >
                🏠 Home
              </button>
            ))}
          <UserMenu />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {showRail && (
          <LeftRail
            activeArea={activeArea}
            onSelectArea={setActiveArea}
            kotTicketsVisible={kdsEnabled}
            openTicketCount={openTicketCount}
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {actionNotice && (
            <p className="flex-none border-b border-border bg-accent-soft px-4 py-1.5 text-xs font-semibold text-accent">
              {actionNotice}
            </p>
          )}

          {activeArea === "billing" &&
            (screen === "order-type" ? (
              <OrderTypeScreen
                sections={sections}
                tables={tables}
                openOrders={openOrders}
                onSelectTable={(table) => void selectCustomerSlot(table, "Customer-1")}
                onSelectNonSeating={handleSelectNonSeating}
              />
            ) : (
              <ItemCartScreen
                draft={draft}
                onBack={resetDraft}
                onSelectCustomer={(selection) => {
                  if (selection.kind === "direct" && selection.tableId) {
                    const table = tables.find((t) => t.id === selection.tableId);
                    if (table) {
                      void selectCustomerSlot(table, "Customer-1");
                      return;
                    }
                  }
                  void handleSelectTable(selection);
                }}
                onOpenBilling={setBillingMode}
              />
            ))}

          {activeArea === "kot-tickets" && <KotTicketsScreen onSelectOrder={handleSelectOrderFromList} />}

          {activeArea === "fast-billing" && (
            <FastBillingScreen
              tables={tables}
              waiters={waiters}
              sections={sections}
              waiterLocked={isWaiterRole}
              waiterMandatory={waiterMandatory}
              allItems={draft.allItems}
              onSelectTable={handleSelectTable}
              onSelectWaiter={handleSelectWaiter}
              onAddItemByCode={draft.resolveAndAddItemByCode}
              onDone={() => {
                setActiveArea("billing");
                setScreen(tableId || sectionId ? "item-cart" : "order-type");
              }}
            />
          )}

          {activeArea === "recall" && (
            <RecallScreen locationId={location?.id ?? null} onSelectOrder={handleSelectOrderFromList} />
          )}
        </div>
      </div>

      {pendingWaiterFor && (
        <WaiterPickerModal
          waiters={waiters}
          onSelect={(w) => void handleWaiterPicked(w)}
          onClose={handleWaiterPopupCancel}
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
    </div>
  );
}
