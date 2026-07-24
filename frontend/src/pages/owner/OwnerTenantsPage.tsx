import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Repeat } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { createTenant, listTenants, updateTenant } from "@/api/platformTenants";
import { listPlans } from "@/api/platformPlans";
import { changeSubscriptionPlan } from "@/api/platformSubscriptions";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { ChangePlanModal } from "@/features/owner/ChangePlanModal";
import { TenantFormModal } from "@/features/owner/TenantFormModal";
import { toast } from "@/store/toastStore";
import type { PlanCode } from "@/types/plan";
import type { Tenant, TenantCreate } from "@/types/tenant";
import { getApiErrorMessage } from "@/utils/apiError";

const PLAN_BADGE_VARIANT: Record<PlanCode, "lite" | "pro" | "pro_max"> = {
  lite: "lite",
  pro: "pro",
  pro_max: "pro_max",
};

export default function OwnerTenantsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [suspending, setSuspending] = useState<Tenant | null>(null);
  const [isSuspending, setIsSuspending] = useState(false);
  const [changingPlanFor, setChangingPlanFor] = useState<Tenant | null>(null);
  const [isChangingPlan, setIsChangingPlan] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["platform-tenants", page, search],
    queryFn: () => listTenants({ page, page_size: 20, search: search || undefined }),
  });

  const { data: plans } = useQuery({ queryKey: ["platform-plans-all"], queryFn: () => listPlans() });

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
  }

  async function handleCreate(payload: TenantCreate) {
    setIsSubmitting(true);
    try {
      await createTenant(payload);
      await invalidate();
      setFormOpen(false);
      toast("success", t("owner.tenants.created"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggleSuspend(tenant: Tenant) {
    if (tenant.status === "active") {
      setSuspending(tenant);
      return;
    }
    try {
      await updateTenant(tenant.id, { status: "active" });
      await invalidate();
      toast("success", t("owner.tenants.reactivated"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    }
  }

  async function confirmSuspend() {
    if (!suspending) return;
    setIsSuspending(true);
    try {
      await updateTenant(suspending.id, { status: "suspended" });
      await invalidate();
      setSuspending(null);
      toast("success", t("owner.tenants.suspended"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSuspending(false);
    }
  }

  async function handleChangePlan(planId: string) {
    if (!changingPlanFor) return;
    setIsChangingPlan(true);
    try {
      await changeSubscriptionPlan(changingPlanFor.subscription_id, { plan_id: planId });
      await invalidate();
      setChangingPlanFor(null);
      toast("success", t("owner.subscriptions.planChanged"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("owner.subscriptions.changePlanError")));
    } finally {
      setIsChangingPlan(false);
    }
  }

  function formatUsage(count: number, limit: number): string {
    return limit === -1 ? `${count} / ${t("owner.tenants.unlimited")}` : `${count} / ${limit}`;
  }

  const columns: Column<Tenant>[] = [
    {
      key: "name",
      header: t("owner.tenants.storeName"),
      render: (tenant) => (
        <div>
          <p className="font-medium text-slate-900">{tenant.name}</p>
          <p className="text-xs text-slate-500">{tenant.owner_email}</p>
        </div>
      ),
    },
    {
      key: "plan",
      header: t("owner.tenants.plan"),
      render: (tenant) => (
        <div className="flex items-center gap-2">
          <Badge variant={PLAN_BADGE_VARIANT[tenant.plan_code]}>{t(`plans.${tenant.plan_code}`)}</Badge>
          {tenant.has_pending_upgrade_request && (
            <Badge variant="info">{t("owner.tenants.upgradeRequested")}</Badge>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: t("common.status"),
      render: (tenant) => (
        <Badge variant={tenant.status === "active" ? "success" : "danger"}>
          {t(`owner.tenants.statuses.${tenant.status}`)}
        </Badge>
      ),
    },
    {
      key: "users",
      header: t("owner.tenants.users"),
      render: (tenant) => formatUsage(tenant.usage.users_count, tenant.usage.users_limit),
    },
    {
      key: "stores",
      header: t("owner.tenants.stores"),
      render: (tenant) => formatUsage(tenant.usage.stores_count, tenant.usage.stores_limit),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (tenant) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setChangingPlanFor(tenant)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("owner.subscriptions.changePlanTitle", { name: tenant.name })}
          >
            <Repeat className="h-4 w-4" />
          </button>
          <Button variant="outline" size="sm" onClick={() => void handleToggleSuspend(tenant)}>
            {tenant.status === "active" ? t("owner.tenants.suspend") : t("owner.tenants.reactivate")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("owner.tenants.title")}
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("owner.tenants.addButton")}
          </Button>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(t2) => t2.id}
        isLoading={isLoading}
        emptyMessage={t("owner.tenants.empty")}
        search={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder={t("owner.tenants.searchPlaceholder")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <TenantFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleCreate}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={suspending !== null}
        onOpenChange={(open) => !open && setSuspending(null)}
        title={t("owner.tenants.suspendConfirmTitle")}
        body={t("owner.tenants.suspendConfirmBody", { name: suspending?.name })}
        isConfirming={isSuspending}
        onConfirm={() => void confirmSuspend()}
      />

      {changingPlanFor && (
        <ChangePlanModal
          open={changingPlanFor !== null}
          onOpenChange={(open) => !open && setChangingPlanFor(null)}
          tenantName={changingPlanFor.name}
          currentPlanId={changingPlanFor.plan_id}
          plans={plans ?? []}
          onSubmit={handleChangePlan}
          isSubmitting={isChangingPlan}
        />
      )}
    </div>
  );
}
