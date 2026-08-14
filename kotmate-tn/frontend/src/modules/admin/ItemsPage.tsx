import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type ChangeEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { resolveAssetUrl } from "@/lib/api";
import { listCategories } from "@/modules/admin/categoriesApi";
import {
  type Item,
  type ItemCreatePayload,
  type ItemImportResult,
  createItem,
  downloadItemsCsv,
  getSectionPrices,
  importItemsCsv,
  listItems,
  restockItem,
  setSectionPrices,
  updateItem,
  uploadItemImage,
} from "@/modules/admin/itemsApi";
import { listTaxRules } from "@/modules/admin/taxRulesApi";
import { me } from "@/modules/auth/authApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

// Small size on purpose (CLAUDE.md §9 dense grid, many items on screen at once) — well
// under the server's own 5MB ceiling (MAX_UPLOAD_SIZE_BYTES), which stays as a backstop.
const MAX_IMAGE_BYTES = 1024 * 1024;

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

type ItemSortKey = "code" | "name" | "category" | "price" | "flags";

// Item codes are typically numeric (CLAUDE.md §9 laminated-menu code entry, e.g. "301")
// but stored as free text, so compare numerically when both sides parse and fall back to
// a plain string compare otherwise (e.g. non-numeric legacy codes).
function compareItemCode(a: string | null, b: string | null): number {
  if (!a && !b) return 0;
  if (!a) return -1;
  if (!b) return 1;
  const na = Number(a);
  const nb = Number(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  return a.localeCompare(b);
}

// Flags sort groups Top Selling + Combo tiles together (more flags first), then falls
// back to name so ties within the same flag combination stay predictable.
function flagScore(item: Item): number {
  return (item.is_top_seller ? 2 : 0) + (item.is_combo_tile ? 1 : 0);
}

function sortItems(
  items: Item[],
  key: ItemSortKey,
  dir: "asc" | "desc",
  categoryNameById: Map<string, string>,
): Item[] {
  const sorted = [...items].sort((a, b) => {
    switch (key) {
      case "code":
        return compareItemCode(a.item_code, b.item_code);
      case "name":
        return a.name_en.localeCompare(b.name_en);
      case "category":
        return (categoryNameById.get(a.category_id) ?? "").localeCompare(
          categoryNameById.get(b.category_id) ?? "",
        );
      case "price":
        return a.price - b.price;
      case "flags": {
        const diff = flagScore(b) - flagScore(a);
        return diff !== 0 ? diff : a.name_en.localeCompare(b.name_en);
      }
      default:
        return 0;
    }
  });
  return dir === "asc" ? sorted : sorted.reverse();
}

function suggestNextItemCode(items: Item[]): string {
  const nums = items
    .map((i) => i.item_code)
    .filter((code): code is string => !!code)
    .map(Number)
    .filter((n) => !Number.isNaN(n));
  if (nums.length === 0) return "";
  return String(Math.max(...nums) + 1);
}

interface ItemFormState {
  name_en: string;
  name_ta: string;
  category_id: string;
  price: string;
  tax_class_id: string;
  item_code: string;
  is_top_seller: boolean;
  is_combo_tile: boolean;
  track_inventory: boolean;
  available_qty: string;
}

function formFromItem(item: Item): ItemFormState {
  return {
    name_en: item.name_en,
    name_ta: item.name_ta ?? "",
    category_id: item.category_id,
    price: item.price.toString(),
    tax_class_id: item.tax_class_id ?? "",
    item_code: item.item_code ?? "",
    is_top_seller: item.is_top_seller,
    is_combo_tile: item.is_combo_tile,
    track_inventory: item.track_inventory,
    available_qty: item.available_qty?.toString() ?? "",
  };
}

function emptyForm(defaultCategoryId: string, suggestedItemCode: string): ItemFormState {
  return {
    name_en: "",
    name_ta: "",
    category_id: defaultCategoryId,
    price: "",
    tax_class_id: "",
    item_code: suggestedItemCode,
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
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!sections) return;
    const initial: Record<string, string> = {};
    for (const s of sections) initial[s.section_id] = s.override_price?.toString() ?? "";
    setDrafts(initial);
    setSavedIds(new Set());
  }, [sections]);

  const saveAllMutation = useMutation({
    mutationFn: () =>
      setSectionPrices(
        itemId,
        Object.entries(drafts).map(([section_id, price]) => ({
          section_id,
          price: price ? Number(price) : null,
        })),
      ),
    onSuccess: () => {
      setSavedIds(new Set(Object.keys(drafts)));
      void queryClient.invalidateQueries({ queryKey: ["section-prices", itemId] });
    },
  });

  function updateDraft(sectionId: string, value: string) {
    setDrafts((d) => ({ ...d, [sectionId]: value }));
    setSavedIds((s) => {
      if (!s.has(sectionId)) return s;
      const next = new Set(s);
      next.delete(sectionId);
      return next;
    });
  }

  if (!sections) return <p className="text-xs text-foreground/50">Loading sections…</p>;

  return (
    <div className="flex flex-col gap-2">
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
              onChange={(e) => updateDraft(section.section_id, e.target.value)}
            />
            <span className="text-xs text-foreground/50">Resolved: ₹{section.resolved_price}</span>
            {savedIds.has(section.section_id) && (
              <span className="text-xs font-semibold text-accent">Saved ✓</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={saveAllMutation.isPending}
          onClick={() => saveAllMutation.mutate()}
          className="self-start rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-accent-foreground disabled:opacity-60"
        >
          {saveAllMutation.isPending ? "Saving…" : "Save All Section Prices"}
        </button>
      </div>
    </div>
  );
}

function ItemImageEditor({
  item,
  onUploaded,
}: {
  item: Item;
  onUploaded: () => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);

  const imageMutation = useMutation({
    mutationFn: (file: File) => uploadItemImage(item.id, file),
    onSuccess: onUploaded,
    onError: (err) => setImageError(apiErrorMessage(err, "Failed to upload image.")),
  });

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageError(null);
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError(
        `Image is ${(file.size / 1024 / 1024).toFixed(1)}MB — please use one under ${MAX_IMAGE_BYTES / 1024 / 1024}MB.`,
      );
      e.target.value = "";
      return;
    }
    setPreviewUrl(URL.createObjectURL(file));
    imageMutation.mutate(file);
  }

  const displayUrl = previewUrl ?? item.image_url;

  return (
    <div className="flex items-center gap-3">
      {displayUrl && (
        <img
          src={resolveAssetUrl(displayUrl)}
          alt={item.name_en}
          className="h-20 w-20 rounded-md border border-border object-cover"
        />
      )}
      <div className="flex flex-col gap-1">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          className="text-xs"
        />
        <p className="text-[11px] text-foreground/50">
          Max {MAX_IMAGE_BYTES / 1024 / 1024}MB — keep it small, the POS grid shows many items at once.
        </p>
        {imageMutation.isPending && <p className="text-xs text-foreground/50">Uploading…</p>}
        {imageError && <p className="text-xs text-chili">{imageError}</p>}
      </div>
    </div>
  );
}

function ItemFormModal({
  editingItem,
  categories,
  taxRules,
  itemImagesEnabled,
  sectionPricingEnabled,
  stockManagementEnabled,
  suggestedItemCode,
  onClose,
}: {
  editingItem: Item | null;
  categories: { id: string; name_en: string }[];
  taxRules: { id: string; name: string }[];
  itemImagesEnabled: boolean;
  sectionPricingEnabled: boolean;
  stockManagementEnabled: boolean;
  suggestedItemCode: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  // `item` is the persisted row we're now editing — null only for a brand-new item that
  // hasn't been saved yet. The first successful Save in "add" mode flips this to the
  // newly created item (Admin-5) so image upload / per-section pricing become available
  // immediately, without closing and reopening the modal.
  const [item, setItem] = useState<Item | null>(editingItem);
  const [form, setForm] = useState<ItemFormState>(
    editingItem ? formFromItem(editingItem) : emptyForm(categories[0]?.id ?? "", suggestedItemCode),
  );
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["items"] });

  function buildPayload(): ItemCreatePayload {
    return {
      name_en: form.name_en,
      name_ta: form.name_ta || undefined,
      category_id: form.category_id,
      price: Number(form.price),
      tax_class_id: form.tax_class_id || null,
      item_code: form.item_code || undefined,
      is_top_seller: form.is_top_seller,
      is_combo_tile: form.is_combo_tile,
      track_inventory: form.track_inventory,
      available_qty: form.track_inventory && form.available_qty ? Number(form.available_qty) : null,
    };
  }

  const createMutation = useMutation({
    mutationFn: () => createItem(buildPayload()),
    onSuccess: (created) => {
      invalidate();
      setItem(created);
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to create item.")),
  });

  const updateMutation = useMutation({
    mutationFn: () => updateItem(item!.id, buildPayload()),
    onSuccess: (updated) => {
      invalidate();
      setItem(updated);
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to update item.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (item) {
      updateMutation.mutate();
    } else {
      createMutation.mutate();
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{item ? "Edit Item" : "Add Item"}</h2>

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

          <div className="grid grid-cols-4 gap-3">
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
              <label className={labelClass}>Tax Class</label>
              <select
                className={inputClass}
                value={form.tax_class_id}
                onChange={(e) => setForm((f) => ({ ...f, tax_class_id: e.target.value }))}
              >
                <option value="">Default</option>
                {taxRules.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
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
                disabled={!stockManagementEnabled}
                onChange={(e) => setForm((f) => ({ ...f, track_inventory: e.target.checked }))}
              />
              Track stock count
            </label>
            {!stockManagementEnabled && (
              <p className="text-xs text-foreground/50">
                Stock management is off for your account — a tenant_admin can turn it on in Settings.
              </p>
            )}
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

          <div className="flex justify-end border-t border-border pt-3">
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-accent-foreground disabled:opacity-60"
            >
              {isPending ? "Saving…" : item ? "Save Name/Price Changes" : "Create Item to Continue"}
            </button>
          </div>

          <div className="border-t border-border pt-3">
            <h3 className="mb-2 text-sm font-semibold">Item Image</h3>
            {item ? (
              itemImagesEnabled ? (
                <ItemImageEditor item={item} onUploaded={invalidate} />
              ) : (
                <p className="text-xs text-foreground/50">
                  Item images aren't available on your current plan — upgrade to Pro to add photos.
                </p>
              )
            ) : (
              <p className="text-xs text-foreground/50">Save the item above first to add a photo.</p>
            )}
          </div>

          <div className="border-t border-border pt-3">
            <h3 className="mb-2 text-sm font-semibold">Per-Section Price Override</h3>
            {item ? (
              sectionPricingEnabled ? (
                <SectionPriceEditor itemId={item.id} basePrice={item.price} />
              ) : (
                <p className="text-xs text-foreground/50">
                  Per-section pricing isn't available on your current plan — upgrade to Pro to reprice
                  items per seating section (e.g. AC vs Non-AC).
                </p>
              )
            ) : (
              <p className="text-xs text-foreground/50">Save the item above first to set section prices.</p>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              {item ? "Done" : "Cancel"}
            </button>
          </div>
        </form>
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

function ImportPanel({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<ItemImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => importItemsCsv(file),
    onSuccess: (res) => {
      setResult(res);
      void queryClient.invalidateQueries({ queryKey: ["items"] });
    },
    onError: (err) => setError(apiErrorMessage(err, "Import failed.")),
  });

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setResult(null);
    mutation.mutate(file);
  }

  return (
    <div className="mb-4 rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Import Items from CSV</h3>
        <button type="button" onClick={onClose} className="text-xs font-semibold hover:underline">
          Close
        </button>
      </div>
      <p className="mb-2 text-xs text-foreground/60">
        Columns: item_code, name_en, name_ta, category, price, tax_class, is_top_seller, is_combo_tile.
        Matches existing items by item_code (updates them); new codes create new items. Images aren't
        handled by import — add those individually after.
      </p>
      <input type="file" accept=".csv,text/csv" onChange={handleFileChange} className="text-xs" />
      {mutation.isPending && <p className="mt-2 text-xs text-foreground/50">Importing…</p>}
      {error && <p className="mt-2 text-xs text-chili">{error}</p>}
      {result && (
        <div className="mt-2 text-xs">
          <p className="font-semibold text-accent">
            {result.created} created, {result.updated} updated.
          </p>
          {result.errors.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-chili">
              {result.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function ItemsPage() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [formItem, setFormItem] = useState<Item | null | "new">(null);
  const [restockingItem, setRestockingItem] = useState<Item | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<ItemSortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const exportErrorTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const { data: taxRules = [] } = useQuery({ queryKey: ["tax-rules"], queryFn: listTaxRules });
  const { data: items, isLoading, isError } = useQuery({
    queryKey: ["items", categoryFilter, search],
    queryFn: () =>
      listItems({ category_id: categoryFilter || undefined, search: search || undefined }),
  });

  const categoryNameById = useMemo(
    () => new Map(categories.map((c) => [c.id, c.name_en])),
    [categories],
  );
  const sortedItems = useMemo(
    () => (items ? sortItems(items, sortKey, sortDir, categoryNameById) : items),
    [items, sortKey, sortDir, categoryNameById],
  );

  function handleSort(key: ItemSortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function sortIndicator(key: ItemSortKey): string {
    if (key !== sortKey) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  }
  const itemImagesEnabled = meData?.features?.item_images === true;
  const sectionPricingEnabled = meData?.features?.section_pricing === true;
  const stockManagementEnabled = meData?.stock_tracking_enabled === true;
  const itemExportEnabled = meData?.features?.item_export === true;
  const itemImportEnabled = meData?.features?.item_import === true;

  const toggleActiveMutation = useMutation({
    mutationFn: (item: Item) => updateItem(item.id, { is_active: !item.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["items"] }),
  });

  async function handleExport() {
    try {
      await downloadItemsCsv();
    } catch (err) {
      setExportError(apiErrorMessage(err, "Export failed."));
      if (exportErrorTimeout.current) clearTimeout(exportErrorTimeout.current);
      exportErrorTimeout.current = setTimeout(() => setExportError(null), 4000);
    }
  }

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="mt-1 text-xl font-bold">Item Master</h1>
          <p className="text-sm text-foreground/60">
            {meData?.plan_code === "lite" ? "Lite plan — images & section pricing locked" : "Pro features unlocked"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {itemExportEnabled && (
            <button
              type="button"
              onClick={() => void handleExport()}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              Export CSV
            </button>
          )}
          {itemImportEnabled && (
            <button
              type="button"
              onClick={() => setShowImport((v) => !v)}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              Import CSV
            </button>
          )}
          <button
            type="button"
            onClick={() => setFormItem("new")}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
          >
            + Add Item
          </button>
        </div>
      </div>

      {exportError && <p className="mb-4 text-sm text-chili">{exportError}</p>}
      {showImport && <ImportPanel onClose={() => setShowImport(false)} />}

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
                <th className="cursor-pointer select-none px-4 py-2.5 hover:text-foreground" onClick={() => handleSort("code")}>
                  Code{sortIndicator("code")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2.5 hover:text-foreground" onClick={() => handleSort("name")}>
                  Name{sortIndicator("name")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2.5 hover:text-foreground" onClick={() => handleSort("category")}>
                  Category{sortIndicator("category")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2.5 hover:text-foreground" onClick={() => handleSort("price")}>
                  Price{sortIndicator("price")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2.5 hover:text-foreground" onClick={() => handleSort("flags")}>
                  Flags{sortIndicator("flags")}
                </th>
                <th className="px-4 py-2.5">Stock</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(sortedItems ?? []).map((item) => (
                <tr key={item.id} className={`border-t border-border ${item.is_active ? "" : "opacity-50"}`}>
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
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        item.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {item.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button type="button" onClick={() => setFormItem(item)} className="text-accent hover:underline">
                        Edit
                      </button>
                      {item.track_inventory && stockManagementEnabled && (
                        <button
                          type="button"
                          onClick={() => setRestockingItem(item)}
                          className="text-accent hover:underline"
                        >
                          Restock
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => toggleActiveMutation.mutate(item)}
                        className={item.is_active ? "text-chili hover:underline" : "text-accent hover:underline"}
                      >
                        {item.is_active ? "Deactivate" : "Reactivate"}
                      </button>
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
          taxRules={taxRules}
          itemImagesEnabled={itemImagesEnabled}
          sectionPricingEnabled={sectionPricingEnabled}
          stockManagementEnabled={stockManagementEnabled}
          suggestedItemCode={formItem === "new" ? suggestNextItemCode(items ?? []) : ""}
          onClose={() => setFormItem(null)}
        />
      )}
      {restockingItem && (
        <RestockDialog item={restockingItem} onClose={() => setRestockingItem(null)} />
      )}
    </div>
  );
}
