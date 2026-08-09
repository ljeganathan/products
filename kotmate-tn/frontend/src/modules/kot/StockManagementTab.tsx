import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";

import { listCategories } from "@/modules/admin/categoriesApi";
import { listStockItems, type StockItem, updateStockItem } from "@/modules/kot/stockApi";

// KOT screen's second tab (extends Phase 05/08's soft-inventory feature, Pro/Pro Max
// only) — every active item, searchable/grouped by category, with an inline qty input
// that both sets the count and turns tracking on for that item (one action).
export function StockManagementTab() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const {
    data: items = [],
    isLoading,
    isError,
    error,
  } = useQuery({ queryKey: ["stock-items"], queryFn: listStockItems, retry: false });

  const saveMutation = useMutation({
    mutationFn: ({ itemId, qty }: { itemId: string; qty: number }) => updateStockItem(itemId, qty),
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
              return (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3.5 py-2.5"
                >
                  <span className="min-w-0 flex-1 truncate text-sm">
                    <span className="font-bold">{item.name_en}</span>
                    {item.name_ta && <span className="ml-1.5 text-ink-faint">{item.name_ta}</span>}
                  </span>
                  <input
                    type="number"
                    min={0}
                    value={draft ?? currentValue}
                    onChange={(e) => setDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    className="w-24 rounded-md border border-border bg-background px-2 py-1.5 text-right text-sm"
                  />
                  <button
                    type="button"
                    disabled={!isDirty || draft === "" || saveMutation.isPending}
                    onClick={() => saveMutation.mutate({ itemId: item.id, qty: Number(draft) })}
                    className="rounded-md border border-accent bg-accent-soft px-3 py-1.5 text-xs font-bold text-accent disabled:opacity-40"
                  >
                    Save
                  </button>
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
