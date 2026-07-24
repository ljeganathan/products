import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Power, Upload } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listCategories } from "@/api/categories";
import { createItem, deactivateItem, listItems, updateItem } from "@/api/items";
import { listStock } from "@/api/stock";
import { listTaxProfiles } from "@/api/taxProfiles";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { BulkImportModal } from "@/features/items/BulkImportModal";
import { ItemFormModal } from "@/features/items/ItemFormModal";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { Item, ItemCreate } from "@/types/item";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";
import { stockStatusVariant } from "@/utils/stockStatus";

export default function ItemsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const storeId = useAuthStore((s) => s.user?.store_id ?? undefined);

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Item | null>(null);
  const [deactivatingItem, setDeactivatingItem] = useState<Item | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeactivating, setIsDeactivating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["items", page, search, storeId],
    queryFn: () => listItems({ page, page_size: 20, search: search || undefined, store_id: storeId }),
  });
  const { data: categoriesData } = useQuery({
    queryKey: ["categories-all"],
    queryFn: () => listCategories({ page: 1, page_size: 100 }),
  });
  const { data: taxProfiles } = useQuery({
    queryKey: ["tax-profiles-all"],
    queryFn: () => listTaxProfiles(),
  });
  const { data: stockData } = useQuery({
    queryKey: ["stock-for-items", storeId],
    queryFn: () => listStock({ page_size: 100, store_id: storeId }),
  });

  const categories = categoriesData?.items ?? [];
  const categoryNameById = new Map(categories.map((c) => [c.id, c.name_en]));
  const taxProfileNameById = new Map((taxProfiles ?? []).map((p) => [p.id, p.name]));
  const stockByItemId = new Map((stockData?.items ?? []).map((s) => [s.item_id, s]));

  function openAdd() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function openEdit(item: Item) {
    setEditingItem(item);
    setFormOpen(true);
  }

  async function handleSubmit(payload: ItemCreate) {
    setIsSubmitting(true);
    try {
      if (editingItem) {
        await updateItem(editingItem.id, payload);
      } else {
        await createItem(payload);
      }
      await queryClient.invalidateQueries({ queryKey: ["items"] });
      await queryClient.invalidateQueries({ queryKey: ["stock-for-items"] });
      setFormOpen(false);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeactivate() {
    if (!deactivatingItem) return;
    setIsDeactivating(true);
    try {
      await deactivateItem(deactivatingItem.id);
      await queryClient.invalidateQueries({ queryKey: ["items"] });
      setDeactivatingItem(null);
      toast("success", t("items.deactivateSuccess"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsDeactivating(false);
    }
  }

  const columns: Column<Item>[] = [
    { key: "barcode", header: t("items.barcode"), render: (i) => i.barcode ?? "—" },
    {
      key: "name",
      header: t("items.name"),
      render: (i) => (
        <div>
          <p className="font-medium text-slate-900">{i.name_en}</p>
          <p className="text-sm text-slate-500">{i.name_ta}</p>
        </div>
      ),
    },
    {
      key: "category",
      header: t("items.category"),
      render: (i) => categoryNameById.get(i.category_id) ?? "—",
    },
    { key: "brand", header: t("items.brand"), render: (i) => i.brand ?? "—" },
    { key: "pack_size", header: t("items.packSize"), render: (i) => i.pack_size ?? "—" },
    { key: "mrp", header: t("items.mrp"), render: (i) => formatPaise(i.mrp_paise) },
    {
      key: "selling_price",
      header: t("items.sellingPrice"),
      render: (i) => formatPaise(i.selling_price_paise),
    },
    {
      key: "tax_slab",
      header: t("items.taxSlab"),
      render: (i) => taxProfileNameById.get(i.tax_profile_id) ?? "—",
    },
    {
      key: "stock",
      header: t("items.stockOnHand"),
      render: (i) => {
        const stock = stockByItemId.get(i.id);
        if (!stock) return "—";
        return (
          <Badge variant={stockStatusVariant(stock.quantity_on_hand, i.reorder_level)}>
            {stock.quantity_on_hand} {i.unit}
          </Badge>
        );
      },
    },
    { key: "reorder_level", header: t("items.reorderLevel"), render: (i) => i.reorder_level },
    {
      key: "status",
      header: t("common.status"),
      render: (i) => (
        <Badge variant={i.is_active ? "success" : "neutral"}>
          {i.is_active ? t("common.active") : t("common.inactive")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (i) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => openEdit(i)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("common.edit")}
          >
            <Pencil className="h-4 w-4" />
          </button>
          {i.is_active && (
            <button
              type="button"
              onClick={() => setDeactivatingItem(i)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
              aria-label={t("items.deactivate")}
            >
              <Power className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("items.title")}
        actions={
          <>
            <Button variant="outline" onClick={() => setBulkImportOpen(true)}>
              <Upload className="h-4 w-4" />
              {t("items.bulkImport")}
            </Button>
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4" />
              {t("items.addButton")}
            </Button>
          </>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(i) => i.id}
        isLoading={isLoading}
        emptyMessage={t("items.empty")}
        search={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder={t("items.searchPlaceholder")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <ItemFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        item={editingItem}
        categories={categories}
        taxProfiles={taxProfiles ?? []}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      <BulkImportModal
        open={bulkImportOpen}
        onOpenChange={setBulkImportOpen}
        onImported={() => {
          void queryClient.invalidateQueries({ queryKey: ["items"] });
          void queryClient.invalidateQueries({ queryKey: ["stock-for-items"] });
        }}
      />

      <ConfirmModal
        open={deactivatingItem !== null}
        onOpenChange={(open) => !open && setDeactivatingItem(null)}
        title={t("items.deactivateConfirmTitle")}
        body={t("items.deactivateConfirmBody", { name: deactivatingItem?.name_en })}
        confirmLabel={t("items.deactivate")}
        isConfirming={isDeactivating}
        onConfirm={() => void handleDeactivate()}
      />
    </div>
  );
}
