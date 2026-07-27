import { useQuery } from "@tanstack/react-query";
import { Download, Lock } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { downloadSalesCsv, getGstSummary, getSalesReport } from "@/api/reports";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { DateRangePicker, type DateRange } from "@/features/dashboard/DateRangePicker";
import { SalesTrendChart } from "@/features/dashboard/SalesTrendChart";
import { StatTile } from "@/features/dashboard/StatTile";
import { toast } from "@/store/toastStore";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";

function defaultRange(): DateRange {
  const to = new Date().toISOString().slice(0, 10);
  const from = new Date();
  from.setDate(from.getDate() - 6);
  return { dateFrom: from.toISOString().slice(0, 10), dateTo: to };
}

export default function ReportsPage() {
  const { t } = useTranslation();
  const [range, setRange] = useState<DateRange>(defaultRange());
  const [isExporting, setIsExporting] = useState(false);

  const salesQuery = useQuery({
    queryKey: ["reports-sales", range],
    queryFn: () => getSalesReport({ date_from: range.dateFrom, date_to: range.dateTo }),
  });
  const gstQuery = useQuery({
    queryKey: ["reports-gst", range],
    queryFn: () => getGstSummary({ date_from: range.dateFrom, date_to: range.dateTo }),
  });

  async function handleExportCsv() {
    setIsExporting(true);
    try {
      await downloadSalesCsv({ date_from: range.dateFrom, date_to: range.dateTo });
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("reports.exportError")));
    } finally {
      setIsExporting(false);
    }
  }

  const sales = salesQuery.data;
  const gst = gstQuery.data;
  const isRangeUpgradeRequired = sales?.range_clamped === true;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("reports.title")}
        subtitle={t("reports.subtitle")}
        actions={
          <Button
            variant="outline"
            onClick={() => void handleExportCsv()}
            isLoading={isExporting}
            disabled={isRangeUpgradeRequired}
          >
            <Download className="h-4 w-4" />
            {t("reports.exportCsv")}
          </Button>
        }
      />

      {isRangeUpgradeRequired ? (
        <div className="flex flex-col items-start justify-between gap-3 rounded-xl border border-warning-200 bg-warning-50 p-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <Lock className="h-5 w-5 shrink-0 text-warning-600" />
            <div>
              <p className="text-sm font-medium text-warning-900">{t("reports.upgradeTitle")}</p>
              <p className="text-sm text-warning-700">{t("reports.upgradeBody")}</p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/settings/subscription">{t("dashboard.upgradeCta")}</Link>
          </Button>
        </div>
      ) : (
        <DateRangePicker value={range} onChange={setRange} />
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label={t("dashboard.sales")} value={formatPaise(sales?.total_paise ?? 0)} />
        <StatTile label={t("dashboard.bills")} value={String(sales?.bill_count ?? 0)} />
        <StatTile
          label={t("dashboard.avgBillValue")}
          value={formatPaise(sales?.avg_bill_paise ?? 0)}
        />
        <StatTile label={t("reports.profit")} value={formatPaise(sales?.profit_paise ?? 0)} />
        <StatTile label={t("reports.cgstSgst")} value={formatPaise((gst?.cgst_paise ?? 0) + (gst?.sgst_paise ?? 0))} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
        <p className="mb-3 text-sm font-medium text-slate-700">{t("dashboard.salesTrend")}</p>
        <SalesTrendChart data={sales?.daily ?? []} groupBy="day" />
      </div>

      {gst && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
          <p className="mb-3 text-sm font-medium text-slate-700">{t("reports.gstSummaryTitle")}</p>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">{t("reports.subtotal")}</dt>
              <dd className="font-medium text-slate-900">{formatPaise(gst.subtotal_paise)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("reports.discount")}</dt>
              <dd className="font-medium text-slate-900">{formatPaise(gst.discount_paise)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("reports.cgst")}</dt>
              <dd className="font-medium text-slate-900">{formatPaise(gst.cgst_paise)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("reports.sgst")}</dt>
              <dd className="font-medium text-slate-900">{formatPaise(gst.sgst_paise)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("reports.grandTotal")}</dt>
              <dd className="font-medium text-slate-900">{formatPaise(gst.total_paise)}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
