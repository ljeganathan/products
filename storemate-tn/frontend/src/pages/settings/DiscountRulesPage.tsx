import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { Lock, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listCategories } from "@/api/categories";
import { createDiscountRule, deleteDiscountRule, listDiscountRules } from "@/api/discountRules";
import { listItems } from "@/api/items";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { DiscountRuleFormModal } from "@/features/settings/DiscountRuleFormModal";
import { toast } from "@/store/toastStore";
import type { DiscountRule, DiscountRuleCreate } from "@/types/discountRule";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";

export default function DiscountRulesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState<DiscountRule | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["discount-rules"],
    queryFn: () => listDiscountRules({ page_size: 50 }),
    retry: (count, err) => isAxiosError(err) && err.response?.status !== 403 && count < 3,
  });
  const { data: items } = useQuery({
    queryKey: ["items-all"],
    queryFn: () => listItems({ page_size: 100 }),
    enabled: !isError,
  });
  const { data: categories } = useQuery({
    queryKey: ["categories-all"],
    queryFn: () => listCategories({ page_size: 100 }),
    enabled: !isError,
  });

  const isUpgradeRequired = isError && isAxiosError(error) && error.response?.status === 403;

  const itemNameById = new Map((items?.items ?? []).map((i) => [i.id, i.name_en]));
  const categoryNameById = new Map((categories?.items ?? []).map((c) => [c.id, c.name_en]));

  async function handleSubmit(payload: DiscountRuleCreate) {
    setIsSubmitting(true);
    try {
      await createDiscountRule(payload);
      await queryClient.invalidateQueries({ queryKey: ["discount-rules"] });
      setFormOpen(false);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setIsDeleting(true);
    try {
      await deleteDiscountRule(deleting.id);
      await queryClient.invalidateQueries({ queryKey: ["discount-rules"] });
      setDeleting(null);
      toast("success", t("common.deleted"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsDeleting(false);
    }
  }

  if (isUpgradeRequired) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title={t("settings.discounts.title")} />
        <EmptyState
          icon={Lock}
          title={t("settings.discounts.upgradeTitle")}
          description={t("settings.discounts.upgradeBody")}
        />
      </div>
    );
  }

  function targetLabel(rule: DiscountRule): string {
    if (rule.scope === "bill") return "—";
    if (rule.scope === "item") return itemNameById.get(rule.target_id ?? "") ?? "—";
    return categoryNameById.get(rule.target_id ?? "") ?? "—";
  }

  const columns: Column<DiscountRule>[] = [
    { key: "scope", header: t("settings.discounts.scope"), render: (r) => t(`settings.discounts.scopes.${r.scope}`) },
    { key: "target", header: t("settings.discounts.target"), render: targetLabel },
    {
      key: "value",
      header: t("settings.discounts.value"),
      render: (r) => (r.type === "flat" ? formatPaise(r.value) : `${(r.value / 100).toFixed(2)}%`),
    },
    {
      key: "period",
      header: t("settings.discounts.period"),
      render: (r) => {
        if (!r.starts_at && !r.ends_at) return t("settings.discounts.alwaysOn");
        const start = r.starts_at ? new Date(r.starts_at).toLocaleDateString("en-IN") : "…";
        const end = r.ends_at ? new Date(r.ends_at).toLocaleDateString("en-IN") : "…";
        return `${start} – ${end}`;
      },
    },
    {
      key: "status",
      header: t("common.status"),
      render: (r) => (
        <Badge variant={r.is_active ? "success" : "neutral"}>
          {r.is_active ? t("common.active") : t("common.inactive")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (r) => (
        <button
          type="button"
          onClick={() => setDeleting(r)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
          aria-label={t("common.delete")}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("settings.discounts.title")}
        subtitle={t("settings.discounts.subtitle")}
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("settings.discounts.addButton")}
          </Button>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(r) => r.id}
        isLoading={isLoading}
        emptyMessage={t("settings.discounts.empty")}
      />

      <DiscountRuleFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        items={items?.items ?? []}
        categories={categories?.items ?? []}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("settings.discounts.deleteConfirmTitle")}
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
