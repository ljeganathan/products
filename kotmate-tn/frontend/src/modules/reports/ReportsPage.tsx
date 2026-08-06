import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { formatINR } from "@/lib/utils";
import { listLocations } from "@/modules/admin/locationsApi";
import { me } from "@/modules/auth/authApi";
import {
  type ExportFormat,
  downloadReportExport,
  getCashierIncentive,
  getCashierWiseSales,
  getCategoryWiseSales,
  getItemWiseSales,
  getSalesSummary,
  getTaxSummary,
  getWaiterIncentive,
  getWaiterWiseSales,
  getZReport,
} from "@/modules/reports/reportsApi";

const inputClass =
  "min-h-9 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";

const REPORTS = [
  { key: "sales-summary", label: "Sales Summary" },
  { key: "item-wise", label: "Item-wise Sales" },
  { key: "category-wise", label: "Category-wise Sales" },
  { key: "tax-summary", label: "Tax Summary" },
  { key: "waiter-wise", label: "Waiter-wise Sales" },
  { key: "cashier-wise", label: "Cashier-wise Sales" },
  { key: "waiter-incentive", label: "Waiter Incentive" },
  { key: "cashier-incentive", label: "Cashier Incentive" },
  { key: "z-report", label: "Z-Report (Shift Close)" },
] as const;
type ReportKey = (typeof REPORTS)[number]["key"];

const EXPORT_LABELS: Record<ExportFormat, string> = { csv: "CSV", excel: "Excel", pdf: "PDF" };

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReportsPage() {
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });

  const [reportKey, setReportKey] = useState<ReportKey>("sales-summary");
  const [dateFrom, setDateFrom] = useState(todayIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [locationId, setLocationId] = useState<string>("");
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);

  const exportFormats = (meData?.features?.export_formats as string[] | undefined) ?? [];
  const params = { date_from: dateFrom, date_to: dateTo, location_id: locationId || undefined };

  const { data, isLoading, isError } = useQuery<unknown>({
    queryKey: ["report", reportKey, params],
    queryFn: (): Promise<unknown> => {
      switch (reportKey) {
        case "sales-summary":
          return getSalesSummary(params);
        case "item-wise":
          return getItemWiseSales(params);
        case "category-wise":
          return getCategoryWiseSales(params);
        case "tax-summary":
          return getTaxSummary(params);
        case "waiter-wise":
          return getWaiterWiseSales(params);
        case "cashier-wise":
          return getCashierWiseSales(params);
        case "waiter-incentive":
          return getWaiterIncentive(params);
        case "cashier-incentive":
          return getCashierIncentive(params);
        case "z-report":
          return getZReport(dateFrom, locationId || undefined);
      }
    },
  });

  async function handleExport(format: ExportFormat) {
    setDownloading(format);
    try {
      const exportParams =
        reportKey === "z-report"
          ? { report_date: dateFrom, location_id: locationId || undefined }
          : params;
      await downloadReportExport(reportKey, exportParams, format);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6">
        <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
          ← Dashboard
        </Link>
        <h1 className="mt-1 text-xl font-bold">Reports</h1>
        <p className="text-sm text-foreground/60">
          Sales, tax, and staff incentive reports for a date range.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {REPORTS.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => setReportKey(r.key)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
              reportKey === r.key
                ? "border-accent bg-accent-soft text-accent"
                : "border-border bg-surface text-foreground/70 hover:border-foreground/30"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-foreground/70">
            {reportKey === "z-report" ? "Date" : "From"}
          </label>
          <input
            type="date"
            className={inputClass}
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        {reportKey !== "z-report" && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-foreground/70">To</label>
            <input
              type="date"
              className={inputClass}
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        )}
        {locations.length > 1 && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-foreground/70">Location</label>
            <select className={inputClass} value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">All locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {exportFormats.length > 0 && (
          <div className="ml-auto flex items-end gap-1.5">
            {exportFormats.map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => handleExport(fmt as ExportFormat)}
                disabled={downloading !== null || !data}
                className="rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-accent/10 disabled:opacity-50"
              >
                {downloading === fmt ? "Exporting…" : `⬇ ${EXPORT_LABELS[fmt as ExportFormat]}`}
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load this report.</p>}
      {data ? <ReportTable reportKey={reportKey} data={data} /> : null}
    </div>
  );
}

const thClass = "px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-foreground/60";
const tdClass = "px-4 py-2.5 text-sm";
const tableWrapClass = "overflow-hidden overflow-x-auto rounded-lg border border-border";
const tableClass = "w-full text-sm";
const theadClass = "bg-foreground/5";
const totalRowClass = "border-t-2 border-border bg-foreground/5 font-bold";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ReportTable({ reportKey, data }: { reportKey: ReportKey; data: any }) {
  switch (reportKey) {
    case "sales-summary":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <tbody>
              <Row label="Bill Count" value={data.bill_count} />
              <Row label="Subtotal" value={formatINR(data.subtotal)} />
              <Row label="Discount" value={formatINR(data.discount_amount)} />
              <Row label="CGST" value={formatINR(data.cgst_amount)} />
              <Row label="SGST" value={formatINR(data.sgst_amount)} />
              <Row label="Round Off" value={formatINR(data.round_off_amount)} />
              <Row label="Grand Total" value={formatINR(data.grand_total)} bold />
              <Row label="Average Bill Value" value={formatINR(data.average_bill_value)} />
            </tbody>
          </table>
        </div>
      );

    case "tax-summary":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <tbody>
              <Row label="Taxable Value" value={formatINR(data.taxable_value)} />
              <Row label="CGST" value={formatINR(data.cgst_amount)} />
              <Row label="SGST" value={formatINR(data.sgst_amount)} />
              <Row label="Total Tax" value={formatINR(data.total_tax)} bold />
            </tbody>
          </table>
        </div>
      );

    case "z-report":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <tbody>
              <Row label="Bill Count" value={data.bill_count} />
              <Row label="Subtotal" value={formatINR(data.subtotal)} />
              <Row label="Discount" value={formatINR(data.discount_amount)} />
              <Row label="CGST" value={formatINR(data.cgst_amount)} />
              <Row label="SGST" value={formatINR(data.sgst_amount)} />
              <Row label="Round Off" value={formatINR(data.round_off_amount)} />
              <Row label="Grand Total" value={formatINR(data.grand_total)} bold />
              {data.payments.map((p: { method: string; amount: number }) => (
                <Row key={p.method} label={`Payment — ${p.method.toUpperCase()}`} value={formatINR(p.amount)} />
              ))}
            </tbody>
          </table>
        </div>
      );

    case "item-wise":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Item</th>
                <th className={`${thClass} text-right`}>Qty Sold</th>
                <th className={`${thClass} text-right`}>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { item_id: string; name_en: string; name_ta: string | null; quantity_sold: number; revenue: number }) => (
                <tr key={r.item_id} className="border-t border-border">
                  <td className={tdClass}>
                    {r.name_en}
                    {r.name_ta && <span className="ml-1.5 text-foreground/50">/ {r.name_ta}</span>}
                  </td>
                  <td className={`${tdClass} text-right tabular-nums`}>{r.quantity_sold}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.revenue)}</td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_revenue)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );

    case "category-wise":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Category</th>
                <th className={`${thClass} text-right`}>Qty Sold</th>
                <th className={`${thClass} text-right`}>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { category_id: string; name_en: string; quantity_sold: number; revenue: number }) => (
                <tr key={r.category_id} className="border-t border-border">
                  <td className={tdClass}>{r.name_en}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{r.quantity_sold}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.revenue)}</td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_revenue)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );

    case "waiter-wise":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Waiter</th>
                <th className={`${thClass} text-right`}>Bills</th>
                <th className={`${thClass} text-right`}>Net Sale Value</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { waiter_id: string; waiter_name: string; bill_count: number; net_sale_value: number }) => (
                <tr key={r.waiter_id} className="border-t border-border">
                  <td className={tdClass}>{r.waiter_name}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{r.bill_count}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.net_sale_value)}</td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_net_sale_value)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );

    case "cashier-wise":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Cashier</th>
                <th className={`${thClass} text-right`}>Bills</th>
                <th className={`${thClass} text-right`}>Net Sale Value</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { pos_user_id: string; name: string; login_id: string; bill_count: number; net_sale_value: number }) => (
                <tr key={r.pos_user_id} className="border-t border-border">
                  <td className={tdClass}>
                    {r.name} <span className="text-foreground/50">({r.login_id})</span>
                  </td>
                  <td className={`${tdClass} text-right tabular-nums`}>{r.bill_count}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.net_sale_value)}</td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_net_sale_value)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );

    case "waiter-incentive":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Waiter</th>
                <th className={`${thClass} text-right`}>Net Sale Value</th>
                <th className={`${thClass} text-right`}>Incentive</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { waiter_id: string; waiter_name: string; net_sale_value: number; incentive_amount: number }) => (
                <tr key={r.waiter_id} className="border-t border-border">
                  <td className={tdClass}>{r.waiter_name}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.net_sale_value)}</td>
                  <td className={`${tdClass} text-right tabular-nums font-bold text-gold`}>
                    {formatINR(r.incentive_amount)}
                  </td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_incentive_amount)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );

    case "cashier-incentive":
      return (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead className={theadClass}>
              <tr>
                <th className={thClass}>Cashier</th>
                <th className={`${thClass} text-right`}>Net Sale Value</th>
                <th className={`${thClass} text-right`}>Incentive</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r: { pos_user_id: string; name: string; login_id: string; net_sale_value: number; incentive_amount: number }) => (
                <tr key={r.pos_user_id} className="border-t border-border">
                  <td className={tdClass}>
                    {r.name} <span className="text-foreground/50">({r.login_id})</span>
                  </td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatINR(r.net_sale_value)}</td>
                  <td className={`${tdClass} text-right tabular-nums font-bold text-gold`}>
                    {formatINR(r.incentive_amount)}
                  </td>
                </tr>
              ))}
              <tr className={totalRowClass}>
                <td className={tdClass}>TOTAL</td>
                <td className={tdClass} />
                <td className={`${tdClass} text-right tabular-nums`}>{formatINR(data.total_incentive_amount)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      );
  }
}

function Row({ label, value, bold }: { label: string; value: string | number; bold?: boolean }) {
  return (
    <tr className="border-t border-border">
      <td className={`${tdClass} ${bold ? "font-bold" : "text-foreground/70"}`}>{label}</td>
      <td className={`${tdClass} text-right tabular-nums ${bold ? "font-bold" : ""}`}>{value}</td>
    </tr>
  );
}
