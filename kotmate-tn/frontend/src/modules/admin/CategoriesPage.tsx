import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type ChangeEvent, type FormEvent, useState } from "react";

import { resolveAssetUrl } from "@/lib/api";
import {
  type Category,
  type CategoryCreatePayload,
  createCategory,
  listCategories,
  reorderCategories,
  updateCategory,
  uploadCategoryIcon,
} from "@/modules/admin/categoriesApi";

const MAX_ICON_BYTES = 1024 * 1024;

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface CategoryFormState {
  name_en: string;
  name_ta: string;
}

function CategoryIconEditor({ category, onUploaded }: { category: Category; onUploaded: () => void }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [iconError, setIconError] = useState<string | null>(null);

  const iconMutation = useMutation({
    mutationFn: (file: File) => uploadCategoryIcon(category.id, file),
    onSuccess: onUploaded,
    onError: (err) => setIconError(apiErrorMessage(err, "Failed to upload icon.")),
  });

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIconError(null);
    if (file.size > MAX_ICON_BYTES) {
      setIconError(`Image is ${(file.size / 1024 / 1024).toFixed(1)}MB — please use one under 1MB.`);
      e.target.value = "";
      return;
    }
    setPreviewUrl(URL.createObjectURL(file));
    iconMutation.mutate(file);
  }

  const displayUrl = previewUrl ?? category.icon_url;

  return (
    <div className="flex items-center gap-3 border-t border-border pt-3">
      {displayUrl && (
        <img
          src={resolveAssetUrl(displayUrl)}
          alt={category.name_en}
          className="h-14 w-14 rounded-md border border-border object-cover"
        />
      )}
      <div className="flex flex-col gap-1">
        <label className={labelClass}>Category Icon (shown on the POS category tab)</label>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          className="text-xs"
        />
        {iconMutation.isPending && <p className="text-xs text-foreground/50">Uploading…</p>}
        {iconError && <p className="text-xs text-chili">{iconError}</p>}
      </div>
    </div>
  );
}

function CategoryFormModal({
  editingCategory,
  onClose,
}: {
  editingCategory: Category | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<Category | null>(editingCategory);
  const [form, setForm] = useState<CategoryFormState>({
    name_en: editingCategory?.name_en ?? "",
    name_ta: editingCategory?.name_ta ?? "",
  });
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["categories"] });

  const mutation = useMutation({
    mutationFn: () => {
      const payload: CategoryCreatePayload = { name_en: form.name_en, name_ta: form.name_ta || undefined };
      return category ? updateCategory(category.id, payload) : createCategory(payload);
    },
    onSuccess: (saved) => {
      invalidate();
      setCategory(saved);
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save category.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{category ? "Edit Category" : "Add Category"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Category Name (English)</label>
              <input
                required
                className={inputClass}
                value={form.name_en}
                onChange={(e) => setForm((f) => ({ ...f, name_en: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>பொருள் வகை பெயர் (தமிழ்)</label>
              <input
                className={inputClass}
                value={form.name_ta}
                onChange={(e) => setForm((f) => ({ ...f, name_ta: e.target.value }))}
              />
            </div>
          </div>

          {error && (
            <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
              {error}
            </p>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-accent-foreground disabled:opacity-60"
            >
              {mutation.isPending ? "Saving…" : category ? "Save Name Changes" : "Create Category to Continue"}
            </button>
          </div>

          {category ? (
            <CategoryIconEditor category={category} onUploaded={invalidate} />
          ) : (
            <p className="border-t border-border pt-3 text-xs text-foreground/50">
              Save the category above first to add an icon.
            </p>
          )}

          <div className="mt-2 flex justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              {category ? "Done" : "Cancel"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function CategoriesPage() {
  const queryClient = useQueryClient();
  const { data: categories, isLoading, isError } = useQuery({
    queryKey: ["categories"],
    queryFn: listCategories,
  });

  const [formCategory, setFormCategory] = useState<Category | null | "new">(null);
  const [dragId, setDragId] = useState<string | null>(null);

  const reorderMutation = useMutation({
    mutationFn: (ordered: Category[]) =>
      reorderCategories(ordered.map((c, index) => ({ id: c.id, display_order: index }))),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["categories"] }),
  });

  function handleDrop(targetId: string) {
    if (!categories || !dragId || dragId === targetId) return;
    const ordered = [...categories];
    const fromIndex = ordered.findIndex((c) => c.id === dragId);
    const toIndex = ordered.findIndex((c) => c.id === targetId);
    const [moved] = ordered.splice(fromIndex, 1);
    ordered.splice(toIndex, 0, moved);
    setDragId(null);
    reorderMutation.mutate(ordered);
  }

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mt-1 text-xl font-bold">Category Master</h1>
          <p className="text-sm text-foreground/60">Drag rows to reorder how they appear in POS</p>
        </div>
        <button
          type="button"
          onClick={() => setFormCategory("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Category
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load categories.</p>}

      {categories && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="w-8 px-4 py-2.5"></th>
                <th className="w-12 px-4 py-2.5">Icon</th>
                <th className="px-4 py-2.5">Name (English)</th>
                <th className="px-4 py-2.5">பெயர் (தமிழ்)</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((category) => (
                <tr
                  key={category.id}
                  draggable
                  onDragStart={() => setDragId(category.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(category.id)}
                  className={`cursor-move border-t border-border ${dragId === category.id ? "opacity-50" : ""}`}
                >
                  <td className="px-4 py-2.5 text-foreground/40">⠿</td>
                  <td className="px-4 py-2.5">
                    {category.icon_url ? (
                      <img
                        src={resolveAssetUrl(category.icon_url)}
                        alt=""
                        className="h-8 w-8 rounded object-cover"
                      />
                    ) : (
                      <span className="text-lg">🍽️</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">{category.name_en}</td>
                  <td className="px-4 py-2.5">{category.name_ta || "—"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        category.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {category.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      onClick={() => setFormCategory(category)}
                      className="text-xs font-semibold text-accent hover:underline"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formCategory && (
        <CategoryFormModal
          editingCategory={formCategory === "new" ? null : formCategory}
          onClose={() => setFormCategory(null)}
        />
      )}
    </div>
  );
}
