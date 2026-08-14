import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import logoMark from "@/assets/logo-mark.png";
import { dispatchPrintJob } from "@/lib/printDispatch";
import { formatINR } from "@/lib/utils";
import { listCategories } from "@/modules/admin/categoriesApi";
import { listLocations } from "@/modules/admin/locationsApi";
import { listTables } from "@/modules/admin/tablesApi";
import { getMyWaiterProfile, listWaiters } from "@/modules/admin/waitersApi";
import { me } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";
import { UserMenu } from "@/modules/auth/UserMenu";
import { BillingModal } from "@/modules/pos/BillingModal";
import { CartPanel } from "@/modules/pos/CartPanel";
import { ALL_ITEMS_ID, CategoryNav, TOP_SELLING_ID } from "@/modules/pos/CategoryNav";
import { ItemCard } from "@/modules/pos/ItemCard";
import { KotTicketsPopup } from "@/modules/pos/KotTicketsPopup";
import { sendOrderToKot } from "@/modules/pos/kotApi";
import {
  type Order,
  type OrderLineInput,
  type PosItem,
  createOrder,
  getItemByCode,
  getOrder,
  listOrders,
  listPosItems,
  listPosSections,
  listTopSellers,
  previewOrderUpdate,
  searchItems,
  updateOrder,
} from "@/modules/pos/posApi";
import { RecallPanel } from "@/modules/pos/RecallPanel";
import { SectionChangeConfirm } from "@/modules/pos/SectionChangeConfirm";
import {
  resolveCustomerSlotSelection,
  type TableSelection,
  TableWaiterBar,
} from "@/modules/pos/TableWaiterBar";
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
  // Persisted so a counter machine that's always billing for the same location doesn't
  // need re-picking after every reload (POS-35); falls back to the tenant's first
  // location until `locations` loads or the stored id no longer matches a real one.
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(() =>
    localStorage.getItem("pos-location-id"),
  );
  const location = locations.find((l) => l.id === selectedLocationId) ?? locations[0];
  useEffect(() => {
    if (location && location.id !== selectedLocationId) {
      setSelectedLocationId(location.id);
      localStorage.setItem("pos-location-id", location.id);
    }
  }, [location, selectedLocationId]);

  function handleLocationChange(nextId: string) {
    localStorage.setItem("pos-location-id", nextId);
    setSelectedLocationId(nextId);
    // Tables/waiters/open-orders are all location-scoped — anything mid-draft on the
    // old location's floor plan can't carry over to the new one.
    setOrder(null);
    setSectionId("");
    setTableId(null);
    setPartyLabel(null);
    if (!isWaiterRole) setWaiterId(null);
  }

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: sections = [] } = useQuery({ queryKey: ["pos-sections"], queryFn: listPosSections });
  const { data: tables = [] } = useQuery({
    queryKey: ["pos-tables", location?.id],
    queryFn: () => listTables({ location_id: location!.id }),
    enabled: !!location,
  });
  const { data: waiters = [] } = useQuery({
    queryKey: ["pos-waiters", location?.id],
    queryFn: () => listWaiters({ location_id: location!.id }),
    enabled: !!location,
  });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const { data: allItems = [] } = useQuery({ queryKey: ["pos-items"], queryFn: () => listPosItems() });
  const { data: topSellers = [] } = useQuery({ queryKey: ["pos-top-sellers"], queryFn: listTopSellers });
  const { data: myWaiterProfile } = useQuery({
    queryKey: ["my-waiter-profile"],
    queryFn: getMyWaiterProfile,
    enabled: role === "waiter",
  });
  // Drives both the occupied-table badges and the party picker (Phase 19, POS-22) — one
  // location-scoped fetch rather than a query per table tap.
  const { data: openOrders = [] } = useQuery({
    queryKey: ["pos-open-orders", location?.id],
    queryFn: () => listOrders({ status: "open", location_id: location!.id }),
    enabled: !!location,
  });

  const [order, setOrder] = useState<Order | null>(null);
  const [sectionId, setSectionId] = useState<string>("");
  const [tableId, setTableId] = useState<string | null>(null);
  const [partyLabel, setPartyLabel] = useState<string | null>(null);
  const [waiterId, setWaiterId] = useState<string | null>(null);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncError, setSyncError] = useState<string | null>(null);

  const [activeCategoryId, setActiveCategoryId] = useState<string>(TOP_SELLING_ID);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PosItem[]>([]);
  const [searchHighlight, setSearchHighlight] = useState(0);
  const [itemCode, setItemCode] = useState("");
  const [itemCodeError, setItemCodeError] = useState<string | null>(null);

  const [openPicker, setOpenPicker] = useState<"table" | "waiter" | null>(null);
  const [showRecall, setShowRecall] = useState(false);
  const [showKotTickets, setShowKotTickets] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [mobileCartOpen, setMobileCartOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [kotSending, setKotSending] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [pendingSectionChange, setPendingSectionChange] = useState<{
    sectionId: string;
    tableId: string | null;
    partyLabel: string | null;
    preview: Order;
  } | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchWrapperRef = useRef<HTMLDivElement>(null);
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
            party_label: partyLabel,
            items: nextItems,
          });
      setOrder(result);
      setSyncState("saved");
      void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
      void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
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

  async function handleSelectSearchResult(item: PosItem) {
    await handleAddItem(item);
    setSearchQuery("");
    searchInputRef.current?.focus();
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
    const code = itemCode.trim();
    if (!code) return;
    setItemCodeError(null);
    // Case-insensitive backend lookup (matches item_service.get_item_by_code) rather
    // than a client-side exact-match scan of `allItems` — that missed any code typed
    // in a different case, or an item added after the initial items load.
    let match: PosItem;
    try {
      match = await getItemByCode(code);
    } catch {
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
    if (fetched.status === "billed") {
      // Defensive: a stale open-orders cache entry can point at an order that's since
      // been billed elsewhere — never load an already-billed order as an editable
      // draft, just refresh the cache and let the caller re-resolve (e.g. as a fresh
      // "new-party" instead of a bogus "resume").
      if (location) void queryClient.invalidateQueries({ queryKey: ["pos-open-orders", location.id] });
      setActionNotice("That ticket has already been billed");
      return;
    }
    const resumed = fetched.status === "held" ? await updateOrder(orderId, { status: "open" }) : fetched;
    setOrder(resumed);
    setSectionId(resumed.section_id);
    setTableId(resumed.table_id);
    setPartyLabel(resumed.party_label);
    setWaiterId(resumed.waiter_id);
  }

  async function handleSelectTable(selection: TableSelection) {
    if (selection.kind === "resume") {
      // Picking up a specific party's existing order (or one from another device) is
      // always a full reload of that order — never a repurposing of whatever draft
      // happened to be in memory (Phase 19, POS-22/POS-25).
      await loadOrderIntoDraft(selection.orderId);
      return;
    }

    if (selection.kind === "new-party") {
      // Starting a fresh customer slot always starts a fresh draft — abandoning the
      // in-memory order here does not affect its persisted state; it stays open on the
      // server and remains reachable via Recall/KOT Tickets or its own customer chip.
      setOrder(null);
      setSectionId(selection.sectionId);
      setTableId(selection.tableId);
      setPartyLabel(selection.partyLabel);
      if (!isWaiterRole) setWaiterId(null);
      return;
    }

    // "direct": either a non-seating section (no table, no customer concept) or a
    // seating table just tapped in the picker.
    const { sectionId: newSectionId, tableId: newTableId } = selection;

    if (newTableId) {
      const table = tables.find((t) => t.id === newTableId);
      if (table) {
        // A draft that hasn't been assigned to any table yet (a walk-in cart started
        // before a table was picked) gets MOVED onto the tapped table under
        // Customer-1, with the usual price-change warning if the section differs —
        // preserves the "start cart, then assign a table" flow. Anything else (no
        // draft, or a draft that's already seated somewhere else) resolves
        // independently instead: resume Customer-1's existing order at the new table,
        // or start fresh there, leaving whatever's currently in the draft untouched
        // and still open server-side (never silently reassigned to a different table).
        if (order && order.items.length > 0 && !tableId) {
          if (newSectionId !== order.section_id) {
            const preview = await previewOrderUpdate(order.id, {
              section_id: newSectionId,
              table_id: newTableId,
            });
            if (preview.subtotal_changed) {
              setPendingSectionChange({
                sectionId: newSectionId,
                tableId: newTableId,
                partyLabel: "Customer-1",
                preview: preview.order,
              });
              return;
            }
          }
          const updated = await updateOrder(order.id, {
            section_id: newSectionId,
            table_id: newTableId,
            party_label: "Customer-1",
          });
          setOrder(updated);
          setSectionId(newSectionId);
          setTableId(newTableId);
          setPartyLabel("Customer-1");
          void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
          return;
        }
        await handleSelectTable(resolveCustomerSlotSelection(table, "Customer-1", openOrders));
        return;
      }
    }

    // Non-seating section (Takeaway/Online Delivery) — unchanged pre-Phase-19/21
    // behaviour, including moving an in-progress draft to a new non-seating section.
    if (order && order.items.length > 0 && newSectionId !== order.section_id) {
      const preview = await previewOrderUpdate(order.id, {
        section_id: newSectionId,
        table_id: newTableId,
      });
      if (preview.subtotal_changed) {
        setPendingSectionChange({
          sectionId: newSectionId,
          tableId: newTableId,
          partyLabel: null,
          preview: preview.order,
        });
        return;
      }
    }
    setSectionId(newSectionId);
    setTableId(newTableId);
    setPartyLabel(null);
    if (order) {
      const updated = await updateOrder(order.id, {
        section_id: newSectionId,
        table_id: newTableId,
        party_label: null,
      });
      setOrder(updated);
      // Table occupancy (the picker's gold badge/count) is driven by this same query —
      // without invalidating it here, a table this order just vacated or claimed keeps
      // showing its pre-move occupancy until an unrelated cart edit happens to refresh it.
      void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
    }
  }

  async function confirmSectionChange() {
    if (!pendingSectionChange || !order) return;
    const updated = await updateOrder(order.id, {
      section_id: pendingSectionChange.sectionId,
      table_id: pendingSectionChange.tableId,
      party_label: pendingSectionChange.partyLabel,
    });
    setOrder(updated);
    setSectionId(pendingSectionChange.sectionId);
    setTableId(pendingSectionChange.tableId);
    setPartyLabel(pendingSectionChange.partyLabel);
    setPendingSectionChange(null);
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
  }

  async function handleSelectWaiter(newWaiterId: string | null) {
    setWaiterId(newWaiterId);
    if (order) {
      const updated = await updateOrder(order.id, { waiter_id: newWaiterId });
      setOrder(updated);
    }
  }

  async function handleClearCart() {
    if (!order) return;
    // Items already sent to the kitchen must never be deleted by "Clear" — this order
    // stays open and reachable via KOT Tickets/Recall exactly as it was; Clear/Esc here
    // just abandons this local draft view of it (same reset as Hold/Bill-finalized).
    if (order.items.some((l) => l.is_kot_sent)) {
      setOrder(null);
      setTableId(null);
      setPartyLabel(null);
      if (!isWaiterRole) setWaiterId(null);
      return;
    }
    if (order.items.length === 0) return;
    await syncCart([]);
  }

  async function handleHold() {
    if (!order) return;
    await updateOrder(order.id, { status: "held" });
    setOrder(null);
    setTableId(null);
    setPartyLabel(null);
    // A waiter login stays locked to themself for the next order; anyone else starts
    // the next bill unassigned rather than showing the just-held order's waiter.
    if (!isWaiterRole) setWaiterId(null);
    setActionNotice("Bill held");
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
  }

  async function handleSendKot() {
    if (!order) return;
    setKotSending(true);
    try {
      const result = await sendOrderToKot(order.id);
      // usb/local_agent KOT printers only get rendered bytes back from the backend —
      // it can't reach that printer itself (it's on the counter/kitchen machine, not
      // the server) — so forward them to the local print-agent or WebUSB here, same as
      // the POS billing flow (lib/printDispatch.ts). A network/wifi printer was already
      // attempted server-side; `print_error` carries why if it failed.
      const printWarning = (await dispatchPrintJob(result.print_job)) ?? result.print_error ?? undefined;
      // Order stays "open" server-side (still reachable via KOT Tickets or by
      // re-picking the same table+customer) — only the local draft/screen clears,
      // the same pattern handleHold already uses, so the cashier is immediately
      // ready for the next table/customer.
      setOrder(null);
      setTableId(null);
      setPartyLabel(null);
      if (!isWaiterRole) setWaiterId(null);
      setActionNotice(
        printWarning
          ? `Sent to kitchen — ticket ${result.ticket_number} — ${printWarning}`
          : `Sent to kitchen — ticket ${result.ticket_number}`,
      );
      void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
    } catch (err) {
      setActionNotice(
        axios.isAxiosError(err) ? String(err.response?.data?.detail ?? err.message) : "Couldn't send to kitchen",
      );
    } finally {
      setKotSending(false);
    }
  }

  function handleBill() {
    if (!order || order.items.length === 0) return;
    setShowBilling(true);
  }

  function handleBillFinalized(printWarning?: string) {
    // Optimistically drop the just-billed order from the open-orders cache immediately
    // — waiting on invalidateQueries' background refetch left a window where the
    // customer chip (CustomerSelectorBar) still resolved to the now-billed order as
    // "resume", loading a closed/uneditable order back into the draft instead of
    // starting fresh for the next customer at that seat.
    const billedOrderId = order?.id;
    if (billedOrderId && location) {
      queryClient.setQueryData<Order[]>(["pos-open-orders", location.id], (prev) =>
        prev ? prev.filter((o) => o.id !== billedOrderId) : prev,
      );
    }
    setShowBilling(false);
    setOrder(null);
    setTableId(null);
    setPartyLabel(null);
    if (!isWaiterRole) setWaiterId(null);
    setActionNotice(printWarning ? `Bill finalized — ${printWarning}` : "Bill finalized");
    void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
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
  const isWaiterRole = role === "waiter";

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
                placeholder="Search items…"
                className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-ink-faint"
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

        {/* KOT Tickets / Recall / Dashboard all fit fine on tablet+, but on a phone
            they were the reason the header overflowed and pushed Dashboard (and
            sometimes Recall too) off-screen with no way to reach them at all — found
            during real-device testing. Below `md` they collapse into the "⋮" menu. */}
        <div className="hidden items-center gap-2.5 md:flex">
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
          {(role === "pos_user" || role === "tenant_admin") && (
            <Link
              to="/dashboard"
              className="flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
            >
              📊 Dashboard
            </Link>
          )}
        </div>

        <div className="relative md:hidden">
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
                {(role === "pos_user" || role === "tenant_admin") && (
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

            <div className="hidden md:flex md:w-80 md:flex-none md:flex-col md:border-l md:border-border lg:w-96">
              <CartPanel
                order={order}
                role={role}
                syncState={syncState}
                onQuantityChange={handleQuantityChange}
                onHold={handleHold}
                onSendKot={handleSendKot}
                onBill={handleBill}
                onClear={() => void handleClearCart()}
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
                onClear={() => void handleClearCart()}
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
