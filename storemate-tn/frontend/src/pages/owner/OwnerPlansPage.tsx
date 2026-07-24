import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listPlans, updatePlan } from "@/api/platformPlans";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlanFormModal } from "@/features/owner/PlanFormModal";
import { toast } from "@/store/toastStore";
import type { Plan, PlanUpdate } from "@/types/plan";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";

export default function OwnerPlansPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Plan | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: plans, isLoading } = useQuery({
    queryKey: ["platform-plans-all"],
    queryFn: () => listPlans(),
  });

  async function handleSubmit(payload: PlanUpdate) {
    if (!editing) return;
    setIsSubmitting(true);
    try {
      await updatePlan(editing.id, payload);
      await queryClient.invalidateQueries({ queryKey: ["platform-plans-all"] });
      setEditing(null);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  function limitLabel(value: number): string {
    return value === -1 ? t("owner.tenants.unlimited") : String(value);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("owner.plans.title")} subtitle={t("owner.plans.subtitle")} />

      {isLoading && <p className="text-slate-500">{t("common.loading")}</p>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {plans?.map((plan) => (
          <div key={plan.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-lg font-semibold text-slate-900">{plan.name}</p>
                <p className="text-2xl font-bold text-brand-700">{formatPaise(plan.price_paise)}</p>
                <p className="text-xs text-slate-500">{t("owner.plans.perMonth")}</p>
              </div>
              <button
                type="button"
                onClick={() => setEditing(plan)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label={t("common.edit")}
              >
                <Pencil className="h-4 w-4" />
              </button>
            </div>

            <dl className="mt-4 flex flex-col gap-1.5 text-sm text-slate-700">
              <div className="flex justify-between">
                <dt>{t("owner.plans.maxUsers")}</dt>
                <dd>{limitLabel(plan.max_users)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t("owner.plans.maxStores")}</dt>
                <dd>{limitLabel(plan.max_stores)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t("owner.plans.maxPrinterProfiles")}</dt>
                <dd>{limitLabel(plan.max_printer_profiles)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t("owner.plans.savedBillDays")}</dt>
                <dd>{limitLabel(plan.saved_bill_days)}</dd>
              </div>
            </dl>

            <div className="mt-4 flex flex-wrap gap-1.5">
              {Object.entries(plan.features_json)
                .filter(([, enabled]) => enabled)
                .map(([key]) => (
                  <Badge key={key} variant="neutral">
                    {t(`owner.plans.featureKeys.${key}`)}
                  </Badge>
                ))}
            </div>
          </div>
        ))}
      </div>

      <PlanFormModal
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        plan={editing}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
