import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Building2, CreditCard, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getPlatformDashboard } from "@/api/platformDashboard";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatTile } from "@/features/dashboard/StatTile";
import { PlanMixChart } from "@/features/owner/PlanMixChart";
import { formatPaise } from "@/utils/money";

export default function OwnerDashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["platform-dashboard"],
    queryFn: () => getPlatformDashboard(),
  });

  if (isLoading || !data) {
    return <p className="text-slate-500">{t("common.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("owner.dashboard.title")}
        subtitle={t("owner.dashboard.subtitle")}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label={t("owner.dashboard.activeTenants")}
          value={String(data.active_tenant_count)}
          icon={Building2}
        />
        <StatTile label={t("owner.dashboard.mrr")} value={formatPaise(data.mrr_paise)} icon={TrendingUp} />
        <StatTile label={t("owner.dashboard.trialing")} value={String(data.trialing_count)} icon={Building2} />
        <StatTile
          label={t("owner.dashboard.churnedThisMonth")}
          value={String(data.churned_this_month_count)}
          icon={AlertTriangle}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
          <p className="mb-3 text-sm font-medium text-slate-700">{t("owner.dashboard.planMix")}</p>
          {data.plan_mix.length > 0 ? (
            <PlanMixChart data={data.plan_mix} />
          ) : (
            <p className="py-8 text-center text-sm text-slate-400">{t("dashboard.noData")}</p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-slate-700">{t("owner.dashboard.overdueInvoices")}</p>
            <CreditCard className="h-4 w-4 text-slate-400" aria-hidden="true" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900">{data.overdue_invoices_count}</p>
          {data.overdue_invoices_count > 0 && (
            <Link
              to="/owner/subscriptions"
              className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              {t("owner.dashboard.reviewSubscriptions")}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
