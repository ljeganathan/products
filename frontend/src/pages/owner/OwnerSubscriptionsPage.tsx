import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Repeat, Settings2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listPlans } from "@/api/platformPlans";
import { changeSubscriptionPlan, listSubscriptions, updateSubscription } from "@/api/platformSubscriptions";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { AddOnFormModal } from "@/features/owner/AddOnFormModal";
import { ChangePlanModal } from "@/features/owner/ChangePlanModal";
import { toast } from "@/store/toastStore";
import type { PlanCode } from "@/types/plan";
import type { Subscription, SubscriptionUpdate } from "@/types/subscription";
import { getApiErrorMessage } from "@/utils/apiError";

const PLAN_BADGE_VARIANT: Record<PlanCode, "lite" | "pro" | "pro_max"> = {
  lite: "lite",
  pro: "pro",
  pro_max: "pro_max",
};

export default function OwnerSubscriptionsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [changingPlanFor, setChangingPlanFor] = useState<Subscription | null>(null);
  const [isChangingPlan, setIsChangingPlan] = useState(false);
  const [editingAddOnsFor, setEditingAddOnsFor] = useState<Subscription | null>(null);
  const [isSavingAddOns, setIsSavingAddOns] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["platform-subscriptions", page],
    queryFn: () => listSubscriptions({ page, page_size: 20 }),
  });

  const { data: plans } = useQuery({ queryKey: ["platform-plans-all"], queryFn: () => listPlans() });

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["platform-subscriptions"] });
  }

  async function handleChangePlan(planId: string) {
    if (!changingPlanFor) return;
    setIsChangingPlan(true);
    try {
      await changeSubscriptionPlan(changingPlanFor.id, { plan_id: planId });
      await invalidate();
      setChangingPlanFor(null);
      toast("success", t("owner.subscriptions.planChanged"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("owner.subscriptions.changePlanError")));
    } finally {
      setIsChangingPlan(false);
    }
  }

  async function handleSaveAddOns(payload: SubscriptionUpdate) {
    if (!editingAddOnsFor) return;
    setIsSavingAddOns(true);
    try {
      await updateSubscription(editingAddOnsFor.id, payload);
      await invalidate();
      setEditingAddOnsFor(null);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSavingAddOns(false);
    }
  }

  const columns: Column<Subscription>[] = [
    {
      key: "tenant",
      header: t("owner.tenants.storeName"),
      render: (sub) => sub.tenant_name,
    },
    {
      key: "plan",
      header: t("owner.tenants.plan"),
      render: (sub) => (
        <div className="flex items-center gap-2">
          <Badge variant={PLAN_BADGE_VARIANT[sub.plan_code]}>{t(`plans.${sub.plan_code}`)}</Badge>
          {sub.requested_plan_code && (
            <Badge variant="info">
              {t("owner.subscriptions.requestedPlan", { plan: t(`plans.${sub.requested_plan_code}`) })}
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: t("common.status"),
      render: (sub) => (
        <Badge variant={sub.status === "active" ? "success" : sub.status === "past_due" ? "warning" : "danger"}>
          {t(`owner.subscriptions.statuses.${sub.status}`)}
        </Badge>
      ),
    },
    {
      key: "period",
      header: t("owner.subscriptions.currentPeriod"),
      render: (sub) => new Date(sub.current_period_end).toLocaleDateString(),
    },
    {
      key: "addons",
      header: t("owner.subscriptions.addOns"),
      render: (sub) =>
        sub.extra_users || sub.extra_stores
          ? t("owner.subscriptions.addOnsSummary", {
              users: sub.extra_users,
              stores: sub.extra_stores,
            })
          : "—",
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (sub) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setChangingPlanFor(sub)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("owner.subscriptions.changePlanTitle", { name: sub.tenant_name })}
          >
            <Repeat className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setEditingAddOnsFor(sub)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("owner.subscriptions.addOnsTitle", { name: sub.tenant_name })}
          >
            <Settings2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("owner.subscriptions.title")} subtitle={t("owner.subscriptions.subtitle")} />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(s) => s.id}
        isLoading={isLoading}
        emptyMessage={t("owner.subscriptions.empty")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      {changingPlanFor && (
        <ChangePlanModal
          open={changingPlanFor !== null}
          onOpenChange={(open) => !open && setChangingPlanFor(null)}
          tenantName={changingPlanFor.tenant_name}
          currentPlanId={changingPlanFor.plan_id}
          plans={plans ?? []}
          onSubmit={handleChangePlan}
          isSubmitting={isChangingPlan}
        />
      )}

      <AddOnFormModal
        open={editingAddOnsFor !== null}
        onOpenChange={(open) => !open && setEditingAddOnsFor(null)}
        subscription={editingAddOnsFor}
        onSubmit={handleSaveAddOns}
        isSubmitting={isSavingAddOns}
      />
    </div>
  );
}
