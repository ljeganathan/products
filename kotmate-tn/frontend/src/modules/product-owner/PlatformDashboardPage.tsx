import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PLAN_LABELS } from "@/lib/constants";
import { formatINR } from "@/lib/utils";
import { getDashboardAlerts, getPlatformMetrics } from "@/modules/product-owner/platformApi";

function KpiCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}

function AlertCard({
  title,
  emptyLabel,
  rows,
}: {
  title: string;
  emptyLabel: string;
  rows: { key: string; to: string; primary: string; secondary: string; badge: string; urgent: boolean }[];
}) {
  return (
    <div className="rounded-lg border border-border p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-foreground/60">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.key}>
              <Link
                to={row.to}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm hover:bg-accent/10"
              >
                <span>
                  <span className="font-medium">{row.primary}</span>
                  <span className="ml-2 text-xs text-foreground/60">{row.secondary}</span>
                </span>
                <span className={`text-xs font-semibold ${row.urgent ? "text-chili" : "text-gold"}`}>
                  {row.badge}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PlatformDashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["platform-metrics"],
    queryFn: getPlatformMetrics,
  });
  const { data: alerts } = useQuery({
    queryKey: ["platform-dashboard-alerts"],
    queryFn: getDashboardAlerts,
  });

  if (isLoading) return <p className="text-sm text-foreground/60">Loading…</p>;
  if (isError || !data) return <p className="text-sm text-chili">Failed to load metrics.</p>;

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Active Tenants" value={String(data.active_tenant_count)} accent="text-accent" />
        <KpiCard label="MRR Estimate" value={formatINR(data.mrr_estimate)} accent="text-gold" />
        <KpiCard
          label="Seat Usage"
          value={`${data.total_active_users} / ${data.total_max_users ?? "∞"}`}
          accent="text-accent"
        />
        <KpiCard
          label="Location Usage"
          value={`${data.total_active_locations} / ${data.total_max_locations}`}
          accent="text-chili"
        />
      </div>

      {alerts && (
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <AlertCard
            title="Expiring / Expired Subscriptions"
            emptyLabel="No subscriptions expiring in the next 7 days."
            rows={alerts.expiring_subscriptions.map((sub) => ({
              key: sub.tenant_id,
              to: `/platform/tenants/${sub.tenant_id}`,
              primary: sub.company_name,
              secondary: sub.plan_code ? PLAN_LABELS[sub.plan_code] : "",
              badge: sub.days_remaining < 0 ? `Expired ${-sub.days_remaining}d ago` : `${sub.days_remaining}d left`,
              urgent: sub.days_remaining < 0,
            }))}
          />
          <AlertCard
            title="Overdue Invoices"
            emptyLabel="No overdue invoices."
            rows={alerts.overdue_invoices.map((inv) => ({
              key: inv.invoice_id,
              to: `/platform/tenants/${inv.tenant_id}`,
              primary: inv.company_name,
              secondary: `${inv.invoice_number} · ${formatINR(inv.amount)}`,
              badge: `${inv.days_overdue}d overdue`,
              urgent: true,
            }))}
          />
        </div>
      )}
    </div>
  );
}
