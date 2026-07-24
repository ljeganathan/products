import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { createCategory, deleteCategory, listCategories, updateCategory } from "@/api/categories";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { CategoryFormModal } from "@/features/categories/CategoryFormModal";
import { toast } from "@/store/toastStore";
import type { Category, CategoryCreate } from "@/types/category";
import { getApiErrorMessage } from "@/utils/apiError";

export default function CategoriesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [deletingCategory, setDeletingCategory] = useState<Category | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["categories", page, search],
    queryFn: () => listCategories({ page, page_size: 20, search: search || undefined }),
  });

  const { data: allCategories } = useQuery({
    queryKey: ["categories-all"],
    queryFn: () => listCategories({ page: 1, page_size: 100 }),
  });

  function openAdd() {
    setEditingCategory(null);
    setFormOpen(true);
  }

  function openEdit(category: Category) {
    setEditingCategory(category);
    setFormOpen(true);
  }

  async function handleSubmit(payload: CategoryCreate) {
    setIsSubmitting(true);
    try {
      if (editingCategory) {
        await updateCategory(editingCategory.id, payload);
      } else {
        await createCategory(payload);
      }
      await queryClient.invalidateQueries({ queryKey: ["categories"] });
      await queryClient.invalidateQueries({ queryKey: ["categories-all"] });
      setFormOpen(false);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deletingCategory) return;
    setIsDeleting(true);
    try {
      await deleteCategory(deletingCategory.id);
      await queryClient.invalidateQueries({ queryKey: ["categories"] });
      await queryClient.invalidateQueries({ queryKey: ["categories-all"] });
      setDeletingCategory(null);
      toast("success", t("common.deleted"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("categories.deleteError")));
    } finally {
      setIsDeleting(false);
    }
  }

  const parentNameById = new Map((allCategories?.items ?? []).map((c) => [c.id, c.name_en]));

  const columns: Column<Category>[] = [
    { key: "name_en", header: t("categories.nameEn"), render: (c) => c.name_en },
    { key: "name_ta", header: t("categories.nameTa"), render: (c) => c.name_ta },
    {
      key: "parent",
      header: t("categories.parentCategory"),
      render: (c) => (c.parent_category_id ? (parentNameById.get(c.parent_category_id) ?? "—") : "—"),
    },
    { key: "hsn", header: t("categories.hsnCode"), render: (c) => c.hsn_code ?? "—" },
    {
      key: "actions",
      header: t("common.actions"),
      render: (c) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => openEdit(c)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("common.edit")}
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setDeletingCategory(c)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
            aria-label={t("common.delete")}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("categories.title")}
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" />
            {t("categories.addButton")}
          </Button>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(c) => c.id}
        isLoading={isLoading}
        emptyMessage={t("categories.empty")}
        search={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder={t("categories.searchPlaceholder")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <CategoryFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        category={editingCategory}
        categories={allCategories?.items ?? []}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={deletingCategory !== null}
        onOpenChange={(open) => !open && setDeletingCategory(null)}
        title={t("categories.deleteConfirmTitle")}
        body={t("categories.deleteConfirmBody", { name: deletingCategory?.name_en })}
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
