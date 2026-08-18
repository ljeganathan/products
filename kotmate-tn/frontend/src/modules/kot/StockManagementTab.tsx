import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";

import { listCategories } from "@/modules/admin/categoriesApi";
import { listStockItems, type StockItem, updateStockItem } from "@/modules/kot/stockApi";

// "+" popup next to an item's qty box — enter a quantity to ADD to whatever's
// currently in the box (e.g. 3 + 50 -> 53), rather than typing the final total by
// hand. Purely a client-side convenience: it just writes the computed sum into the
// same draft state the existing Save button already persists, no new endpoint.
function AddStockPopup({
  currentValue,
  onConfirm,
  onClose,
}: {
  currentValue: number;
  onConfirm: (increment: number) => void;
  onClose: () => void;
}) {
  const [amount, setAmount] = useState("");
  const parsed = Number(amount);
  const valid = amount !== "" && !Number.isNaN(parsed) && parsed > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-xs rounded-lg bg-background p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-1 text-sm font-bold">Add Stock</h3>
        <p className="mb-3 text-xs text-ink-faint">Currently {currentValue} — enter how many to add.</p>
        <input
          autoFocus
          type="number"
          min={1}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && valid) onConfirm(parsed);
          }}
          placeholder="e.g. 50"
          className="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-right text-sm outline-none"
        />
        {valid && (
          <p className="mt-1.5 text-xs text-ink-faint">
            New total: <span className="font-bold text-foreground">{currentValue + parsed}</span>
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
            disabled={!valid}
            onClick={() => onConfirm(parsed)}
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-bold text-accent-foreground disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

// KOT screen's second tab (extends Phase 05/08's soft-inventory feature, Pro/Pro Max
// only) — every active item, searchable/grouped by category, with an inline qty input
// that both sets the count and turns tracking on for that item (one action).
export function StockManagementTab() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [addStockItemId, setAddStockItemId] = useState<string | null>(null);

  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const {
    data: items = [],
    isLoading,
    isError,
    error,
  } = useQuery({ queryKey: ["stock-items"], queryFn: listStockItems, retry: false });

  const saveMutation = useMutation({
    mutationFn: ({ itemId, qty }: { itemId: string; qty: number | null }) => updateStockItem(itemId, qty),
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
                  {addStockItemId === item.id && (
                    <AddStockPopup
                      currentValue={Number(draft ?? currentValue) || 0}
                      onClose={() => setAddStockItemId(null)}
                      onConfirm={(increment) => {
                        const newValue = (Number(draft ?? currentValue) || 0) + increment;
                        setDrafts((prev) => ({ ...prev, [item.id]: String(newValue) }));
                        setAddStockItemId(null);
                      }}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {!isLoading && filtered.length === 0 && <p className="text-sm text-ink-faint">No items found.</p>}
    </div>
  );
}
