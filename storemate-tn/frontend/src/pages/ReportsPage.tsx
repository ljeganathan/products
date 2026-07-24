import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

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

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("reports.title")}
        subtitle={t("reports.subtitle")}
        actions={
          <Button variant="outline" onClick={() => void handleExportCsv()} isLoading={isExporting}>
            <Download className="h-4 w-4" />
            {t("reports.exportCsv")}
          </Button>
        }
      />

      <DateRangePicker value={range} onChange={setRange} />

      {sales?.range_clamped && (
        <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-800">
          {t("reports.rangeClampedNotice")}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label={t("dashboard.sales")} value={formatPaise(sales?.total_paise ?? 0)} />
        <StatTile label={t("dashboard.bills")} value={String(sales?.bill_count ?? 0)} />
        <StatTile
          label={t("dashboard.avgBillValue")}
          value={formatPaise(sales?.avg_bill_paise ?? 0)}
        />
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
