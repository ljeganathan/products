import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { createTaxProfile, deleteTaxProfile, listTaxProfiles, updateTaxProfile } from "@/api/taxProfiles";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { TaxProfileFormModal } from "@/features/settings/TaxProfileFormModal";
import { toast } from "@/store/toastStore";
import type { TaxProfile, TaxProfileCreate } from "@/types/item";
import { getApiErrorMessage } from "@/utils/apiError";

export default function TaxSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<TaxProfile | null>(null);
  const [deleting, setDeleting] = useState<TaxProfile | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: profiles, isLoading } = useQuery({
    queryKey: ["tax-profiles-all"],
    queryFn: () => listTaxProfiles(),
  });

  async function handleSubmit(payload: TaxProfileCreate) {
    setIsSubmitting(true);
    try {
      if (editing) {
        await updateTaxProfile(editing.id, payload);
      } else {
        await createTaxProfile(payload);
      }
      await queryClient.invalidateQueries({ queryKey: ["tax-profiles-all"] });
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
      await deleteTaxProfile(deleting.id);
      await queryClient.invalidateQueries({ queryKey: ["tax-profiles-all"] });
      setDeleting(null);
      toast("success", t("common.deleted"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("settings.tax.deleteError")));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("settings.tax.title")}
        subtitle={t("settings.tax.subtitle")}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            {t("settings.tax.addButton")}
          </Button>
        }
      />

      {isLoading && <p className="text-slate-500">{t("common.loading")}</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {profiles?.map((p) => (
          <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-slate-900">{p.name}</p>
                <p className="mt-1 text-sm text-slate-500">
                  CGST {p.cgst_pct}% + SGST {p.sgst_pct}%
                </p>
              </div>
              {p.is_default && <Badge variant="success">{t("settings.tax.default")}</Badge>}
            </div>
            {p.warning && <p className="mt-2 text-xs text-warning-700">{p.warning}</p>}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setEditing(p);
                  setFormOpen(true);
                }}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label={t("common.edit")}
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setDeleting(p)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
                aria-label={t("common.delete")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <TaxProfileFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        profile={editing}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("settings.tax.deleteConfirmTitle")}
        body={t("settings.tax.deleteConfirmBody", { name: deleting?.name })}
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
