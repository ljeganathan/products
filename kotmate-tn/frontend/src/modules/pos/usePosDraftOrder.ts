import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import { listLocations } from "@/modules/admin/locationsApi";
import { listTables } from "@/modules/admin/tablesApi";
import { getMyWaiterProfile, listWaiters } from "@/modules/admin/waitersApi";
import { me } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";
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
  updateOrder,
} from "@/modules/pos/posApi";
import { resolveCustomerSlotSelection, type TableSelection } from "@/modules/pos/TableWaiterBar";
import { usePosWebSocket } from "@/modules/pos/usePosWebSocket";
import { sendOrderToKot } from "@/modules/pos/kotApi";
import { dispatchPrintJob } from "@/lib/printDispatch";
import { listCategories } from "@/modules/admin/categoriesApi";

type SyncState = "idle" | "saving" | "saved" | "error";

function toLineInputs(order: Order | null): OrderLineInput[] {
  if (!order) return [];
  return order.items.map((line) => ({
    id: line.id,
    item_id: line.item_id,
    quantity: line.quantity,
    notes: line.notes,
  }));
}

// The order/table/waiter/cart data layer shared by every POS layout (Default's
// POSPage.tsx and Guided POS's GuidedPOSPage.tsx) — table/customer-slot resolution,
// repeat-KOT-safe cart sync, section-change price-recalc confirmation, hold/KOT/clear —
// is subtle enough (Phase 07/08/19/21 production feedback baked in) that duplicating it
// for a second layout risks silently diverging behavior. Deliberately excludes anything
// UI-shell-specific to Default (search/item-code-field state, F-key shortcuts, mobile
// menu) — those stay local to each page since the two layouts present them differently.
export function usePosDraftOrder() {
  const role = useAuthStore((s) => s.role)!;
  const isWaiterRole = role === "waiter";
  const queryClient = useQueryClient();

  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
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

  const [order, setOrder] = useState<Order | null>(null);
  const [sectionId, setSectionId] = useState<string>("");
  const [tableId, setTableId] = useState<string | null>(null);
  const [partyLabel, setPartyLabel] = useState<string | null>(null);
  const [waiterId, setWaiterId] = useState<string | null>(null);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncError, setSyncError] = useState<string | null>(null);
  const [kotSending, setKotSending] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [pendingSectionChange, setPendingSectionChange] = useState<{
    sectionId: string;
    tableId: string | null;
    partyLabel: string | null;
    preview: Order;
  } | null>(null);

  function resetDraft() {
    setOrder(null);
    setSectionId("");
    setTableId(null);
    setPartyLabel(null);
    if (!isWaiterRole) setWaiterId(null);
  }

  // Removes a just-billed order from the open-orders cache immediately (production
  // feedback) — waiting on invalidateQueries' background refetch left a window where a
  // customer-slot chip still resolved to the now-billed order as "resume".
  function dropOrderFromOpenOrdersCache(orderId: string) {
    if (!location) return;
    queryClient.setQueryData<Order[]>(["pos-open-orders", location.id], (prev) =>
      prev ? prev.filter((o) => o.id !== orderId) : prev,
    );
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
  const { data: topSellers = [] } = useQuery({
    queryKey: ["pos-top-sellers"],
    queryFn: listTopSellers,
    refetchInterval: 60_000,
  });
  const { data: myWaiterProfile } = useQuery({
    queryKey: ["my-waiter-profile"],
    queryFn: getMyWaiterProfile,
    enabled: role === "waiter",
  });
  const { data: openOrders = [] } = useQuery({
    queryKey: ["pos-open-orders", location?.id],
    queryFn: () => listOrders({ status: "open", location_id: location!.id }),
    enabled: !!location,
  });

  const stockOverrides = usePosWebSocket(location?.id);

  useEffect(() => {
    if (role === "waiter") {
      setWaiterId(myWaiterProfile ? myWaiterProfile.id : null);
    }
  }, [role, myWaiterProfile]);

  useEffect(() => {
    if (!actionNotice) return;
    const t = setTimeout(() => setActionNotice(null), 3500);
    return () => clearTimeout(t);
  }, [actionNotice]);

  // "Require waiter selection" is a single tenant-wide setting common to both POS
  // layouts (production feedback — previously hardcoded always-mandatory on Default
  // and a Guided-POS-only toggle). Non-seating orders (Takeaway/Online Delivery) never
  // require a waiter on either layout, regardless of this setting. Defaults true while
  // /auth/me is still loading, matching the pre-existing always-mandatory behavior.
  const waiterMandatory = meData?.waiter_mandatory_enabled !== false;
  const readyToOrder =
    Boolean(sectionId) && (isWaiterRole || tableId === null || !waiterMandatory || Boolean(waiterId));
  const missingSelectionMessage = !sectionId
    ? "Select a table or Takeaway first"
    : !readyToOrder
      ? "Assign a waiter first"
      : null;

  function handleLocationChange(nextId: string) {
    localStorage.setItem("pos-location-id", nextId);
    setSelectedLocationId(nextId);
    resetDraft();
  }

  function resolvedPriceFor(item: PosItem): number {
    const line = order?.items.find((l) => l.item_id === item.id);
    return line ? line.unit_price : item.price;
  }

  function quantityInCartFor(item: PosItem): number {
    return (
      order?.items
        .filter((l) => l.item_id === item.id && !l.notes)
        .reduce((sum, l) => sum + l.quantity, 0) ?? 0
    );
  }

  function isOutOfStock(item: PosItem): boolean {
    const override = stockOverrides[item.id];
    const qty = override?.available_qty ?? item.available_qty;
    return item.track_inventory && qty !== null && qty <= 0;
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

  async function handleAddItem(item: PosItem) {
    if (isOutOfStock(item)) return;
    if (!readyToOrder) {
      setActionNotice(missingSelectionMessage);
      return;
    }
    const current = toLineInputs(order);
    const unsentLine = order?.items.find((l) => l.item_id === item.id && !l.notes && !l.is_kot_sent);
    const next = unsentLine
      ? current.map((l) => (l.id === unsentLine.id ? { ...l, quantity: l.quantity + 1 } : l))
      : [...current, { item_id: item.id, quantity: 1 }];
    await syncCart(next);
  }

  async function handleQuantityChange(lineId: string, newQty: number) {
    const current = toLineInputs(order);
    const next =
      newQty <= 0
        ? current.filter((l) => l.id !== lineId)
        : current.map((l) => (l.id === lineId ? { ...l, quantity: newQty } : l));
    await syncCart(next);
  }

  async function resolveAndAddItemByCode(
    code: string,
  ): Promise<{ ok: true; name: string } | { ok: false; error: string }> {
    let match: PosItem;
    try {
      match = await getItemByCode(code);
    } catch {
      return { ok: false, error: "No item found with that code" };
    }
    if (isOutOfStock(match)) {
      return { ok: false, error: `${match.name_en} is out of stock` };
    }
    await handleAddItem(match);
    return { ok: true, name: match.name_en };
  }

  async function loadOrderIntoDraft(orderId: string) {
    const fetched = await getOrder(orderId);
    if (fetched.status === "billed") {
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
      await loadOrderIntoDraft(selection.orderId);
      return;
    }

    if (selection.kind === "new-party") {
      setOrder(null);
      setSectionId(selection.sectionId);
      setTableId(selection.tableId);
      setPartyLabel(selection.partyLabel);
      // Waiter is deliberately NOT cleared here (production feedback) — switching to a
      // fresh customer slot at the same table keeps whichever waiter was already
      // assigned instead of forcing a reselect; the cashier can still change it via the
      // waiter picker if this new party is actually served by someone else.
      return;
    }

    const { sectionId: newSectionId, tableId: newTableId } = selection;

    if (newTableId) {
      const table = tables.find((t) => t.id === newTableId);
      if (table) {
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

  async function handleSelectWaiter(newWaiterId: string) {
    setWaiterId(newWaiterId);
    if (order) {
      const updated = await updateOrder(order.id, { waiter_id: newWaiterId });
      setOrder(updated);
    }
  }

  async function handleClearCart() {
    if (!order) return;
    if (order.items.some((l) => l.is_kot_sent)) {
      resetDraft();
      return;
    }
    if (order.items.length === 0) return;
    await syncCart([]);
  }

  async function handleHold() {
    if (!order) return;
    await updateOrder(order.id, { status: "held" });
    resetDraft();
    setActionNotice("Bill held");
    void queryClient.invalidateQueries({ queryKey: ["pos-open-orders"] });
  }

  async function handleSendKot(): Promise<void> {
    if (!order) return;
    setKotSending(true);
    try {
      const result = await sendOrderToKot(order.id);
      const printWarning = (await dispatchPrintJob(result.print_job)) ?? result.print_error ?? undefined;
      resetDraft();
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

  return {
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
    stockOverrides,
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
    isOutOfStock,
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
  };
}

export type PosDraftOrder = ReturnType<typeof usePosDraftOrder>;
