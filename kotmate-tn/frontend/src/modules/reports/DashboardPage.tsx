import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatINR } from "@/lib/utils";
import { listLocations } from "@/modules/admin/locationsApi";
import { me } from "@/modules/auth/authApi";
import {
  getDashboardSummary,
  getLowStockItems,
  getMultiLocationComparison,
  getSalesTrend,
} from "@/modules/reports/dashboardApi";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export function DashboardPage() {
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const reportsLevel = (meData?.features?.reports as string | undefined) ?? "basic";
  const hasCharts = reportsLevel !== "basic";
  const hasMultiLocation = reportsLevel === "charts_csv_pdf_excel_multilocation";
  // A cashier keeps Top Selling Items + Low Stock (operationally useful on the floor)
  // but not the sales-figure cards — production feedback, tenant_admin-only otherwise.
  const canSeeSalesFigures = meData?.role !== "pos_user";

  const [locationId, setLocationId] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-summary", locationId],
    queryFn: () => getDashboardSummary({ location_id: locationId || undefined }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-foreground/60">
            {data ? new Date(data.report_date).toLocaleDateString("en-IN", { dateStyle: "full" }) : "Today"}
          </p>
        </div>
        {locations.length > 1 && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-foreground/70">Location</label>
            <select
              className="min-h-9 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent"
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
            >
              <option value="">All locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}

      {data && (
        <>
          {canSeeSalesFigures && (
            <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3">
              <KpiCard label="Today's Sales" value={formatINR(data.today_sales)} />
              <KpiCard label="Bill Count" value={String(data.bill_count)} />
              <KpiCard label="Average Bill Value" value={formatINR(data.average_bill_value)} />
            </div>
          )}

          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-4">
              <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">
                Top Selling Items
              </h2>
              {data.top_items.length === 0 && (
                <p className="text-sm text-foreground/60">No sales yet today.</p>
              )}
              <ul className="flex flex-col gap-1.5">
                {data.top_items.map((item, i) => (
                  <li key={item.item_id} className="flex items-center justify-between text-sm">
                    <span>
                      <span className="mr-2 text-foreground/40">#{i + 1}</span>
                      {item.name_en}
                    </span>
                    <span className="tabular-nums font-semibold">{item.quantity_sold} sold</span>
                  </li>
                ))}
              </ul>
            </div>

            <LowStockSection />
          </div>

          {canSeeSalesFigures &&
            (hasCharts ? (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">
                  Hourly Sales Trend
                </h2>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.hourly_trend}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="hour" tickFormatter={(h: number) => `${h}:00`} fontSize={11} />
                      <YAxis fontSize={11} tickFormatter={(v: number) => `₹${v}`} />
                      <Tooltip
                        // recharts' Formatter type covers array-valued series too, which
                        // this single-series bar chart never produces — narrow loosely
                        // rather than fight its generic signature for a tooltip label.
                        formatter={((v: unknown) => formatINR(Number(v))) as never}
                        labelFormatter={(h: ReactNode) => `${String(h)}:00`}
                      />
                      <Bar dataKey="sales" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <p className="mb-6 rounded-lg border border-dashed border-border bg-surface/50 p-4 text-sm text-foreground/60">
                Charts and trend analysis are available on Pro and Pro Max plans.
              </p>
            ))}
        </>
      )}

      {meData?.role === "tenant_admin" && <SalesTrendSection locationId={locationId} />}

      {hasMultiLocation && meData?.role === "tenant_admin" && <MultiLocationSection />}
    </div>
  );
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/50">{label}</p>
      <p className="mt-1 truncate text-2xl font-extrabold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-foreground/50">{sub}</p>}
    </div>
  );
}

function LowStockSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-low-stock"],
    queryFn: () => getLowStockItems(),
  });

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">Low Stock Items</h2>
      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {data && data.rows.length === 0 && (
        <p className="text-sm text-foreground/60">
          No tracked items are running low — nothing at 5 or fewer remaining.
        </p>
      )}
      {data && data.rows.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {data.rows.map((item) => (
            <li key={item.item_id} className="flex items-center justify-between text-sm">
              <span>
                {item.name_en}
                {item.name_ta && <span className="ml-1.5 text-foreground/50">/ {item.name_ta}</span>}
              </span>
              <span
                className={`tabular-nums font-semibold ${
                  item.available_qty === 0 ? "text-chili" : "text-gold"
                }`}
              >
                {item.available_qty === 0 ? "Out of stock" : `${item.available_qty} left`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SalesTrendSection({ locationId }: { locationId: string }) {
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");

  const { data, isLoading } = useQuery({
    queryKey: ["sales-trend", period, locationId],
    queryFn: () => getSalesTrend({ period, location_id: locationId || undefined }),
  });

  return (
    <div className="mb-6 rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-foreground/60">
          Monthly Sales Trend
        </h2>
        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          {(["monthly", "yearly"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={`rounded px-3 py-1 text-xs font-bold capitalize ${
                period === p ? "bg-accent-soft text-accent" : "text-foreground/60 hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {data && (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.points}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey="label"
                fontSize={11}
                interval={period === "monthly" ? 2 : 0}
                angle={period === "monthly" ? -35 : 0}
                textAnchor={period === "monthly" ? "end" : "middle"}
                height={period === "monthly" ? 40 : 24}
              />
              <YAxis fontSize={11} tickFormatter={(v: number) => `₹${v}`} />
              <Tooltip formatter={((v: unknown) => formatINR(Number(v))) as never} />
              <Bar dataKey="sales" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function MultiLocationSection() {
  const [dateFrom, setDateFrom] = useState(daysAgoIso(6));
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading } = useQuery({
    queryKey: ["multi-location", dateFrom, dateTo],
    queryFn: () => getMultiLocationComparison({ date_from: dateFrom, date_to: dateTo }),
  });

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-foreground/60">
          Multi-Location Comparison
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="min-h-8 rounded-md border border-border bg-background px-2 text-xs"
          />
          <span className="text-xs text-foreground/50">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="min-h-8 rounded-md border border-border bg-background px-2 text-xs"
          />
        </div>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {data && data.rows.length === 0 && (
        <p className="text-sm text-foreground/60">No bills across any location for this range.</p>
      )}
      {data && data.rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Location</th>
                <th className="px-4 py-2.5 text-right">Bills</th>
                <th className="px-4 py-2.5 text-right">Sales</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.location_id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{r.location_name}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{r.bill_count}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{formatINR(r.sales)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
