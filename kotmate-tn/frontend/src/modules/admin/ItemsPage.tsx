import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listCategories } from "@/modules/admin/categoriesApi";
import {
  type Item,
  type ItemCreatePayload,
  type SectionPriceOption,
  createItem,
  getSectionPrices,
  listItems,
  restockItem,
  setSectionPrices,
  updateItem,
  uploadItemImage,
} from "@/modules/admin/itemsApi";
import { me } from "@/modules/auth/authApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface ItemFormState {
  name_en: string;
  name_ta: string;
  category_id: string;
  price: string;
  item_code: string;
  is_top_seller: boolean;
  is_combo_tile: boolean;
  track_inventory: boolean;
  available_qty: string;
}

function emptyForm(defaultCategoryId: string): ItemFormState {
  return {
    name_en: "",
    name_ta: "",
    category_id: defaultCategoryId,
    price: "",
    item_code: "",
    is_top_seller: false,
    is_combo_tile: false,
    track_inventory: false,
    available_qty: "",
  };
}

function SectionPriceEditor({ itemId, basePrice }: { itemId: string; basePrice: number }) {
  const queryClient = useQueryClient();
  const { data: sections } = useQuery({
    queryKey: ["section-prices", itemId],
    queryFn: () => getSectionPrices(itemId),
  });
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!sections) return;
    const initial: Record<string, string> = {};
    for (const s of sections) initial[s.section_id] = s.override_price?.toString() ?? "";
    setDrafts(initial);
  }, [sections]);

  const mutation = useMutation({
    mutationFn: (section: SectionPriceOption) =>
      setSectionPrices(itemId, [
        { section_id: section.section_id, price: drafts[section.section_id] ? Number(drafts[section.section_id]) : null },
      ]),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["section-prices", itemId] }),
  });

  if (!sections) return <p className="text-xs text-foreground/50">Loading sections…</p>;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-3">
      {sections.map((section) => (
        <div key={section.section_id} className="flex items-center gap-3">
          <span className="w-32 text-sm">{section.section_name_en}</span>
          <input
            type="number"
            min={0}
            step="0.01"
            placeholder={`Base ₹${basePrice}`}
            className={`${inputClass} w-32`}
            value={drafts[section.section_id] ?? ""}
            onChange={(e) => setDrafts((d) => ({ ...d, [section.section_id]: e.target.value }))}
          />
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(section)}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10"
          >
            Save
          </button>
          <span className="text-xs text-foreground/50">Resolved: ₹{section.resolved_price}</span>
        </div>
      ))}
    </div>
  );
}

function ItemFormModal({
  editingItem,
  categories,
  itemImagesEnabled,
  sectionPricingEnabled,
  onClose,
}: {
  editingItem: Item | null;
  categories: { id: string; name_en: string }[];
  itemImagesEnabled: boolean;
  sectionPricingEnabled: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ItemFormState>(
    editingItem
      ? {
          name_en: editingItem.name_en,
          name_ta: editingItem.name_ta ?? "",
          category_id: editingItem.category_id,
          price: editingItem.price.toString(),
          item_code: editingItem.item_code ?? "",
          is_top_seller: editingItem.is_top_seller,
          is_combo_tile: editingItem.is_combo_tile,
          track_inventory: editingItem.track_inventory,
          available_qty: editingItem.available_qty?.toString() ?? "",
        }
      : emptyForm(categories[0]?.id ?? ""),
  );
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["items"] });

  const createMutation = useMutation({
    mutationFn: (payload: ItemCreatePayload) => createItem(payload),
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to create item.")),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateItem(editingItem!.id, {
        name_en: form.name_en,
        name_ta: form.name_ta || undefined,
        category_id: form.category_id,
        price: Number(form.price),
        item_code: form.item_code || null,
        is_top_seller: form.is_top_seller,
        is_combo_tile: form.is_combo_tile,
        track_inventory: form.track_inventory,
        available_qty:
          form.track_inventory && form.available_qty ? Number(form.available_qty) : null,
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to update item.")),
  });

  const imageMutation = useMutation({
    mutationFn: (file: File) => uploadItemImage(editingItem!.id, file),
    onSuccess: invalidate,
    onError: (err) => setImageError(apiErrorMessage(err, "Failed to upload image.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (editingItem) {
      updateMutation.mutate();
      return;
    }
    createMutation.mutate({
      name_en: form.name_en,
      name_ta: form.name_ta || undefined,
      category_id: form.category_id,
      price: Number(form.price),
      item_code: form.item_code || undefined,
      is_top_seller: form.is_top_seller,
      is_combo_tile: form.is_combo_tile,
      track_inventory: form.track_inventory,
      available_qty: form.track_inventory && form.available_qty ? Number(form.available_qty) : null,
    });
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingItem ? "Edit Item" : "Add Item"}</h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Item Name (English)</label>
              <input
                required
                className={inputClass}
                value={form.name_en}
                onChange={(e) => setForm((f) => ({ ...f, name_en: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>பொருள் பெயர் (தமிழ்)</label>
              <input
                className={inputClass}
                value={form.name_ta}
                onChange={(e) => setForm((f) => ({ ...f, name_ta: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Category</label>
              <select
                required
                className={inputClass}
                value={form.category_id}
                onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name_en}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Base Price (₹)</label>
              <input
                required
                type="number"
                min={0}
                step="0.01"
                className={inputClass}
                value={form.price}
                onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Item Code</label>
              <input
                placeholder="e.g. 301"
                className={inputClass}
                value={form.item_code}
                onChange={(e) => setForm((f) => ({ ...f, item_code: e.target.value }))}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-5">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_top_seller}
                onChange={(e) => setForm((f) => ({ ...f, is_top_seller: e.target.checked }))}
              />
              Top Selling
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_combo_tile}
                onChange={(e) => setForm((f) => ({ ...f, is_combo_tile: e.target.checked }))}
              />
              Combo / Thali tile
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.track_inventory}
                onChange={(e) => setForm((f) => ({ ...f, track_inventory: e.target.checked }))}
              />
              Track stock count
            </label>
          </div>

          {form.track_inventory && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Available Qty</label>
              <input
                type="number"
                min={0}
                className={`${inputClass} w-40`}
                value={form.available_qty}
                onChange={(e) => setForm((f) => ({ ...f, available_qty: e.target.value }))}
              />
            </div>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {isPending ? "Saving…" : editingItem ? "Save Changes" : "Create Item"}
            </button>
          </div>
        </form>

        {editingItem && (
          <div className="mt-6 flex flex-col gap-2 border-t border-border pt-4">
            <h3 className="text-sm font-semibold">Item Image</h3>
            {itemImagesEnabled ? (
              <>
                {editingItem.image_url && (
                  <img
                    src={editingItem.image_url}
                    alt={editingItem.name_en}
                    className="h-20 w-20 rounded-md border border-border object-cover"
                  />
                )}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setImageError(null);
                      imageMutation.mutate(file);
                    }
                  }}
                />
                {imageMutation.isPending && <p className="text-xs text-foreground/50">Uploading…</p>}
                {imageError && <p className="text-xs text-chili">{imageError}</p>}
              </>
            ) : (
              <p className="text-xs text-foreground/50">
                Item images aren't available on your current plan — upgrade to Pro to add photos.
              </p>
            )}
          </div>
        )}

        {editingItem && (
          <div className="mt-6 flex flex-col gap-2 border-t border-border pt-4">
            <h3 className="text-sm font-semibold">Per-Section Price Override</h3>
            {sectionPricingEnabled ? (
              <SectionPriceEditor itemId={editingItem.id} basePrice={editingItem.price} />
            ) : (
              <p className="text-xs text-foreground/50">
                Per-section pricing isn't available on your current plan — upgrade to Pro to reprice
                items per seating section (e.g. AC vs Non-AC).
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function RestockDialog({ item, onClose }: { item: Item; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [qty, setQty] = useState(item.available_qty?.toString() ?? "0");
  const mutation = useMutation({
    mutationFn: () => restockItem(item.id, Number(qty)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["items"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-3 text-lg font-bold">Restock {item.name_en}</h2>
        <input
          type="number"
          min={0}
          className={`${inputClass} w-full`}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
          >
            {mutation.isPending ? "Saving…" : "Set Stock Count"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ItemsPage() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [formItem, setFormItem] = useState<Item | null | "new">(null);
  const [restockingItem, setRestockingItem] = useState<Item | null>(null);

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const { data: items, isLoading, isError } = useQuery({
    queryKey: ["items", categoryFilter, search],
    queryFn: () =>
      listItems({ category_id: categoryFilter || undefined, search: search || undefined }),
  });

  const categoryNameById = new Map(categories.map((c) => [c.id, c.name_en]));
  const itemImagesEnabled = meData?.features?.item_images === true;
  const sectionPricingEnabled = meData?.features?.section_pricing === true;

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-bold">Item Master</h1>
          <p className="text-sm text-foreground/60">
            {meData?.plan_code === "lite" ? "Lite plan — images & section pricing locked" : "Pro features unlocked"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormItem("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Item
        </button>
      </div>

      <div className="mb-4 flex gap-3">
        <input
          placeholder="Search by name or item code…"
          className={`${inputClass} w-72`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className={inputClass}
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name_en}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load items.</p>}

      {items && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Code</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Category</th>
                <th className="px-4 py-2.5">Price</th>
                <th className="px-4 py-2.5">Flags</th>
                <th className="px-4 py-2.5">Stock</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-mono text-xs">{item.item_code || "—"}</td>
                  <td className="px-4 py-2.5">
                    <div>{item.name_en}</div>
                    {item.name_ta && <div className="text-xs text-foreground/50">{item.name_ta}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {categoryNameById.get(item.category_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">₹{item.price}</td>
                  <td className="px-4 py-2.5 text-xs">
                    <div className="flex gap-1">
                      {item.is_top_seller && (
                        <span className="rounded-full bg-gold/15 px-2 py-0.5 text-gold">Top</span>
                      )}
                      {item.is_combo_tile && (
                        <span className="rounded-full bg-accent/15 px-2 py-0.5 text-accent-foreground">
                          Combo
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    {item.track_inventory ? (
                      <span className={item.available_qty !== null && item.available_qty <= 5 ? "text-chili font-semibold" : ""}>
                        {item.available_qty ?? 0} left
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button type="button" onClick={() => setFormItem(item)} className="text-accent hover:underline">
                        Edit
                      </button>
                      {item.track_inventory && (
                        <button
                          type="button"
                          onClick={() => setRestockingItem(item)}
                          className="text-accent hover:underline"
                        >
                          Restock
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formItem && (
        <ItemFormModal
          editingItem={formItem === "new" ? null : formItem}
          categories={categories}
          itemImagesEnabled={itemImagesEnabled}
          sectionPricingEnabled={sectionPricingEnabled}
          onClose={() => setFormItem(null)}
        />
      )}
      {restockingItem && (
        <RestockDialog item={restockingItem} onClose={() => setRestockingItem(null)} />
      )}
    </div>
  );
}
