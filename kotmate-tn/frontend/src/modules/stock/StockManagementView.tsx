import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";

import { listCategories } from "@/modules/admin/categoriesApi";
import { type StockCalcUnit, listStockItems, type StockItem, updateStockItem } from "@/modules/stock/stockApi";

// Unit families for the "Calculate for Me" mode below — a raw purchase (say, 100 kg of
// rice) and a per-item serving size (say, 500 g per plate) only convert meaningfully
// within the same family (weight<->weight, volume<->volume); "pcs" stands alone for
// items already counted in whole units (e.g. 500 samosas bought / 5 per box).
type UnitFamily = "weight" | "volume" | "count";
interface UnitOption {
  value: string;
  label: string;
  family: UnitFamily;
  // How many of this unit make one base unit for its family (g/ml/pcs = base, so 1).
  toBase: number;
}
const UNITS: UnitOption[] = [
  { value: "g", label: "g", family: "weight", toBase: 1 },
  { value: "kg", label: "kg", family: "weight", toBase: 1000 },
  { value: "ml", label: "ml", family: "volume", toBase: 1 },
  { value: "l", label: "L", family: "volume", toBase: 1000 },
  { value: "pcs", label: "pcs", family: "count", toBase: 1 },
];
const unitsInFamily = (family: UnitFamily) => UNITS.filter((u) => u.family === family);
const unitByValue = (value: string) => UNITS.find((u) => u.value === value)!;
// The "bulk purchase" unit a family is normally bought in (kg of rice, not g; L of oil,
// not ml) — used to pick a sensible default for "Total You Bought" once a remembered
// per-item unit tells us which family this item's conversions live in.
const BULK_UNIT_FOR_FAMILY: Record<UnitFamily, string> = { weight: "kg", volume: "l", count: "pcs" };

// "+" popup next to an item's qty box. Two ways to arrive at how much to add, in one
// screen (production feedback — an earlier version opened the calculator as a second
// popup on top of this one, which felt like an extra detour for a quick counter task):
// type the number directly, or — for a bulk purchase like "bought 100 kg of rice,
// each biriyani uses 500 g" — let the calculator work out "= 200 in stock" instead of
// the cashier doing the division by hand. Either way, it's still purely a client-side
// convenience that writes one number into the same draft state the existing Save
// button already persists — no new endpoint.
function AddStockPopup({
  itemName,
  currentValue,
  rememberedQty,
  rememberedUnit,
  onConfirm,
  onClose,
}: {
  itemName: string;
  currentValue: number;
  // The last "Used Per {item}" value+unit saved for this item (from `items.stock_calc_
  // qty`/`stock_calc_unit`, or a calculation made earlier this session) — pre-fills the
  // calculator instead of asking the cashier to re-derive the same conversion on every
  // restock, and opens straight into Calculate mode since its presence means that's
  // how this item is normally restocked.
  rememberedQty: number | null;
  rememberedUnit: StockCalcUnit | null;
  onConfirm: (increment: number, calc?: { qty: number; unit: StockCalcUnit }) => void;
  onClose: () => void;
}) {
  const hasRemembered = rememberedQty !== null && rememberedUnit !== null;
  const [mode, setMode] = useState<"direct" | "calculate">(hasRemembered ? "calculate" : "direct");

  // Direct-entry mode
  const [amount, setAmount] = useState("");
  const directParsed = Number(amount);
  const directValid = amount !== "" && !Number.isNaN(directParsed) && directParsed > 0;

  // Calculate-for-me mode
  const [totalQty, setTotalQty] = useState("");
  const [totalUnit, setTotalUnit] = useState(
    hasRemembered ? BULK_UNIT_FOR_FAMILY[unitByValue(rememberedUnit).family] : "kg",
  );
  const [perItemQty, setPerItemQty] = useState(hasRemembered ? String(rememberedQty) : "");
  const [perItemUnit, setPerItemUnit] = useState<string>(rememberedUnit ?? "g");

  const totalUnitOption = unitByValue(totalUnit);
  const perItemChoices = unitsInFamily(totalUnitOption.family);
  const totalParsed = Number(totalQty);
  const perItemParsed = Number(perItemQty);
  const calcInputsValid =
    totalQty !== "" && !Number.isNaN(totalParsed) && totalParsed > 0 &&
    perItemQty !== "" && !Number.isNaN(perItemParsed) && perItemParsed > 0;

  let calculatedStock = 0;
  let leftoverBase = 0;
  if (calcInputsValid) {
    const totalBase = totalParsed * totalUnitOption.toBase;
    const perItemBase = perItemParsed * unitByValue(perItemUnit).toBase;
    calculatedStock = Math.floor(totalBase / perItemBase);
    leftoverBase = Math.round((totalBase - calculatedStock * perItemBase) * 100) / 100;
  }

  const finalAmount = mode === "direct" ? directParsed : calculatedStock;
  const finalValid = mode === "direct" ? directValid : calcInputsValid && calculatedStock > 0;

  function handleTotalUnitChange(nextUnit: string) {
    setTotalUnit(nextUnit);
    // Keep the per-item unit inside the same family as Total — switching Total from
    // kg to L, say, would otherwise leave a now-nonsensical "g" still selected below.
    const nextFamily = unitByValue(nextUnit).family;
    if (unitByValue(perItemUnit).family !== nextFamily) {
      setPerItemUnit(unitsInFamily(nextFamily)[0].value);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-lg bg-background p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-1 text-sm font-bold">📦 Add Stock — {itemName}</h3>
        <p className="mb-3 text-xs text-ink-faint">Currently {currentValue}.</p>

        <div className="mb-3 flex gap-1 rounded-lg bg-surface-2 p-1">
          {(["direct", "calculate"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${
                mode === m ? "bg-background text-accent shadow-sm" : "text-ink-faint hover:text-ink-soft"
              }`}
            >
              {m === "direct" ? "🔢 Type Amount" : "🧮 Calculate for Me"}
            </button>
          ))}
        </div>

        {mode === "direct" ? (
          <input
            autoFocus
            type="number"
            min={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && directValid) onConfirm(directParsed);
            }}
            placeholder="e.g. 50"
            className="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-right text-sm outline-none"
          />
        ) : (
          <div className="flex flex-col gap-2.5">
            <div>
              <label className="mb-1 block text-[11px] font-bold text-ink-soft">Total You Bought</label>
              <div className="flex gap-1.5">
                <input
                  autoFocus
                  type="number"
                  min={0}
                  step="any"
                  value={totalQty}
                  onChange={(e) => setTotalQty(e.target.value)}
                  placeholder="e.g. 100"
                  className="w-full min-w-0 flex-1 rounded-md border border-border bg-surface-2 px-3 py-2 text-right text-sm outline-none"
                />
                <select
                  value={totalUnit}
                  onChange={(e) => handleTotalUnitChange(e.target.value)}
                  className="rounded-md border border-border bg-surface-2 px-2 text-sm outline-none"
                >
                  {UNITS.map((u) => (
                    <option key={u.value} value={u.value}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-bold text-ink-soft">Used Per {itemName}</label>
              <div className="flex gap-1.5">
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={perItemQty}
                  onChange={(e) => setPerItemQty(e.target.value)}
                  placeholder="e.g. 500"
                  className="w-full min-w-0 flex-1 rounded-md border border-border bg-surface-2 px-3 py-2 text-right text-sm outline-none"
                />
                <select
                  value={perItemUnit}
                  onChange={(e) => setPerItemUnit(e.target.value)}
                  className="rounded-md border border-border bg-surface-2 px-2 text-sm outline-none"
                >
                  {perItemChoices.map((u) => (
                    <option key={u.value} value={u.value}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="rounded-md bg-accent-soft px-3 py-2 text-center">
              {calcInputsValid ? (
                <>
                  <p className="text-sm font-extrabold text-accent">
                    = {calculatedStock} {itemName} in stock
                  </p>
                  {leftoverBase > 0 && (
                    <p className="text-[11px] text-ink-faint">
                      ({leftoverBase} {unitByValue(perItemUnit).label} left over)
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-ink-faint">Fill both fields to see the stock count</p>
              )}
            </div>
          </div>
        )}

        {finalValid && (
          <p className="mt-2 text-xs text-ink-faint">
            New total: <span className="font-bold text-foreground">{currentValue + finalAmount}</span>
          </p>
        )}
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!finalValid}
            onClick={() =>
              onConfirm(
                finalAmount,
                mode === "calculate"
                  ? { qty: perItemParsed, unit: perItemUnit as StockCalcUnit }
                  : undefined,
              )
            }
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-bold text-accent-foreground disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

// Standalone Stock Management screen (extends Phase 05/08's soft-inventory feature,
// Pro/Pro Max only) — every active item, searchable/grouped by category, with an
// inline qty input that both sets the count and turns tracking on for that item (one
// action). Shared by the main app's own "📦 Stock Management" nav item (Admin/Cashier)
// and the Kitchen Display's Stock Management tab (KOT User, which has no other screen
// to reach a standalone page from — CLAUDE.md §5).
export function StockManagementView() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [addStockItemId, setAddStockItemId] = useState<string | null>(null);
  // Set whenever the "Calculate for Me" popup is confirmed for an item — carried along
  // into that item's next Save so the conversion gets remembered server-side, even
  // though Save itself is a separate click from the popup's own Add.
  const [calcMemory, setCalcMemory] = useState<Record<string, { qty: number; unit: StockCalcUnit }>>({});

  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const {
    data: items = [],
    isLoading,
    isError,
    error,
  } = useQuery({ queryKey: ["stock-items"], queryFn: listStockItems, retry: false });

  const saveMutation = useMutation({
    mutationFn: ({
      itemId,
      qty,
      calc,
    }: {
      itemId: string;
      qty: number | null;
      calc?: { qty: number; unit: StockCalcUnit };
    }) => updateStockItem(itemId, qty, calc),
    onSuccess: (updated) => {
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[updated.id];
        return next;
      });
      void queryClient.invalidateQueries({ queryKey: ["stock-items"] });
      void queryClient.invalidateQueries({ queryKey: ["pos-items"] });
      void queryClient.invalidateQueries({ queryKey: ["kds-tracked-items"] });
    },
  });

  if (isError) {
    const message =
      axios.isAxiosError(error) && error.response?.data?.detail
        ? String(error.response.data.detail)
        : "Stock management isn't available right now.";
    return <p className="p-4 text-sm text-ink-faint">{message}</p>;
  }

  const categoryNameById = new Map(categories.map((c) => [c.id, c.name_en]));
  const q = search.trim().toLowerCase();
  const filtered = items.filter(
    (i) => !q || i.name_en.toLowerCase().includes(q) || (i.name_ta ?? "").toLowerCase().includes(q),
  );
  const grouped = new Map<string, StockItem[]>();
  for (const item of filtered) {
    const key = categoryNameById.get(item.category_id) ?? "Other";
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  const addStockItem = items.find((i) => i.id === addStockItemId);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search items…"
        className="mb-4 w-full max-w-sm rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm outline-none"
      />
      {isLoading && <p className="text-sm text-ink-faint">Loading…</p>}
      {[...grouped.entries()].map(([categoryName, categoryItems]) => (
        <section key={categoryName} className="mb-5">
          <h2 className="mb-2 text-xs font-extrabold uppercase tracking-wide text-ink-faint">
            {categoryName}
          </h2>
          <ul className="flex flex-col gap-1.5">
            {categoryItems.map((item) => {
              const draft = drafts[item.id];
              const currentValue = item.available_qty ?? "";
              const isDirty = draft !== undefined && draft !== String(currentValue);
              // Saving the box blank stops tracking this item entirely (clears
              // track_inventory + available_qty) — the reverse of typing a quantity,
              // which turns tracking on. Only meaningful when clearing a value that was
              // actually there; an already-untracked item's box is blank by default.
              const isClearing = isDirty && draft === "" && item.track_inventory;
              return (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3.5 py-2.5"
                >
                  <span className="min-w-0 flex-1 truncate text-sm">
                    <span className="font-bold">{item.name_en}</span>
                    {item.name_ta && <span className="ml-1.5 text-ink-faint">{item.name_ta}</span>}
                    {isClearing && (
                      <span className="ml-2 text-[11px] font-semibold text-chili">
                        will stop tracking stock
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => setAddStockItemId(item.id)}
                    title="Add to current stock"
                    aria-label={`Add stock for ${item.name_en}`}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-surface-2 text-sm font-extrabold text-ink-soft hover:border-accent hover:text-accent"
                  >
                    +
                  </button>
                  <input
                    type="number"
                    min={0}
                    value={draft ?? currentValue}
                    onChange={(e) => setDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    placeholder="blank = untracked"
                    className="w-24 rounded-md border border-border bg-background px-2 py-1.5 text-right text-sm"
                  />
                  <button
                    type="button"
                    disabled={!isDirty || saveMutation.isPending}
                    onClick={() =>
                      saveMutation.mutate({
                        itemId: item.id,
                        qty: draft === "" ? null : Number(draft),
                        calc: calcMemory[item.id],
                      })
                    }
                    className={`rounded-md border px-3 py-1.5 text-xs font-bold disabled:opacity-40 ${
                      isClearing
                        ? "border-chili bg-chili/10 text-chili"
                        : "border-accent bg-accent-soft text-accent"
                    }`}
                  >
                    {isClearing ? "Stop Tracking" : "Save"}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {!isLoading && filtered.length === 0 && <p className="text-sm text-ink-faint">No items found.</p>}

      {addStockItem && (
        <AddStockPopup
          itemName={addStockItem.name_en}
          currentValue={Number(drafts[addStockItem.id] ?? addStockItem.available_qty ?? 0) || 0}
          rememberedQty={calcMemory[addStockItem.id]?.qty ?? addStockItem.stock_calc_qty}
          rememberedUnit={calcMemory[addStockItem.id]?.unit ?? addStockItem.stock_calc_unit}
          onClose={() => setAddStockItemId(null)}
          onConfirm={(increment, calc) => {
            const currentValue = Number(drafts[addStockItem.id] ?? addStockItem.available_qty ?? 0) || 0;
            setDrafts((prev) => ({ ...prev, [addStockItem.id]: String(currentValue + increment) }));
            if (calc) setCalcMemory((prev) => ({ ...prev, [addStockItem.id]: calc }));
            setAddStockItemId(null);
          }}
        />
      )}
    </div>
  );
}
