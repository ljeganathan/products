import { useQuery } from "@tanstack/react-query";

import { formatINR } from "@/lib/utils";
import { getPlatformMetrics } from "@/modules/product-owner/platformApi";

function KpiCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}

export function PlatformDashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["platform-metrics"],
    queryFn: getPlatformMetrics,
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
    </div>
  );
}
