import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getAvailablePlans, getMySubscription, requestUpgrade } from "@/api/subscription";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { UpgradeRequestModal } from "@/features/settings/UpgradeRequestModal";
import { toast } from "@/store/toastStore";
import type { PlanCode } from "@/types/plan";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";

const PLAN_BADGE_VARIANT: Record<PlanCode, "lite" | "pro" | "pro_max"> = {
  lite: "lite",
  pro: "pro",
  pro_max: "pro_max",
};

function UsageRow({ label, count, limit }: { label: string; count: number; limit: number }) {
  const { t } = useTranslation();
  const isUnlimited = limit === -1;
  const pct = isUnlimited ? 0 : Math.min(100, limit === 0 ? 100 : (count / limit) * 100);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-sm text-slate-700">
        <span>{label}</span>
        <span>{isUnlimited ? `${count} / ${t("owner.tenants.unlimited")}` : `${count} / ${limit}`}</span>
      </div>
      {!isUnlimited && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${pct >= 100 ? "bg-danger-500" : "bg-brand-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}

export default function SubscriptionSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: subscription, isLoading } = useQuery({
    queryKey: ["my-subscription"],
    queryFn: () => getMySubscription(),
  });

  const { data: availablePlans } = useQuery({
    queryKey: ["available-plans"],
    queryFn: () => getAvailablePlans(),
  });

  async function handleUpgradeRequest(planId: string) {
    setIsSubmitting(true);
    try {
      await requestUpgrade({ plan_id: planId });
      await queryClient.invalidateQueries({ queryKey: ["my-subscription"] });
      setUpgradeOpen(false);
      toast("success", t("settings.subscription.requestSent"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading || !subscription) {
    return <p className="text-slate-500">{t("common.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("settings.subscription.title")}
        subtitle={t("settings.subscription.subtitle")}
      />

      <div className="max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={PLAN_BADGE_VARIANT[subscription.plan_code]}>
                {t(`plans.${subscription.plan_code}`)}
              </Badge>
              <span className="text-lg font-semibold text-slate-900">
                {formatPaise(subscription.price_paise)}
                <span className="text-sm font-normal text-slate-500">
                  {t("settings.subscription.perMonth")}
                </span>
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {t("settings.subscription.renewsOn", {
                date: new Date(subscription.current_period_end).toLocaleDateString(),
              })}
            </p>
          </div>
          <Button onClick={() => setUpgradeOpen(true)} disabled={subscription.requested_plan_code !== null}>
            {t("settings.subscription.requestUpgrade")}
          </Button>
        </div>

        {subscription.requested_plan_code && (
          <div className="mt-4 rounded-lg bg-info-50 px-3 py-2 text-sm text-info-800">
            {t("settings.subscription.pendingRequest", {
              plan: t(`plans.${subscription.requested_plan_code}`),
            })}
          </div>
        )}

        <div className="mt-6 flex flex-col gap-4 border-t border-slate-200 pt-4">
          <UsageRow
            label={t("owner.tenants.users")}
            count={subscription.usage.users_count}
            limit={subscription.usage.users_limit}
          />
          <UsageRow
            label={t("owner.tenants.stores")}
            count={subscription.usage.stores_count}
            limit={subscription.usage.stores_limit}
          />
          <UsageRow
            label={t("owner.plans.maxPrinterProfiles")}
            count={subscription.usage.printer_profiles_count}
            limit={subscription.usage.printer_profiles_limit}
          />
        </div>
      </div>

      <UpgradeRequestModal
        open={upgradeOpen}
        onOpenChange={setUpgradeOpen}
        plans={availablePlans ?? []}
        currentPlanCode={subscription.plan_code}
        onSubmit={handleUpgradeRequest}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
