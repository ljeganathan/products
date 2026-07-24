import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import {
  ArrowDown,
  ArrowUp,
  Boxes,
  ChevronRight,
  Download,
  Lock,
  Receipt,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  downloadDashboardPdf,
  getDashboardBreakdown,
  getDashboardStores,
  getDashboardSummary,
  getDashboardTrend,
} from "@/api/dashboard";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { BreakdownChart } from "@/features/dashboard/BreakdownChart";
import { DateRangePicker, type DateRange } from "@/features/dashboard/DateRangePicker";
import { SalesTrendChart } from "@/features/dashboard/SalesTrendChart";
import { StatTile } from "@/features/dashboard/StatTile";
import { StoreTotalsTable } from "@/features/dashboard/StoreTotalsTable";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { BreakdownBy } from "@/types/dashboard";
import { getApiErrorMessage } from "@/utils/apiError";
import { cn } from "@/utils/cn";
import { formatPaise } from "@/utils/money";

function defaultRange(): DateRange {
  const to = new Date().toISOString().slice(0, 10);
  const from = new Date();
  from.setDate(from.getDate() - 6);
  return { dateFrom: from.toISOString().slice(0, 10), dateTo: to };
}

type WidgetKey = "trend" | "breakdown";

export default function DashboardPage() {
  const { t } = useTranslation();
  const userId = useAuthStore((s) => s.user?.id);
  const [range, setRange] = useState<DateRange>(defaultRange());
  const [breakdownBy, setBreakdownBy] = useState<BreakdownBy>("payment_mode");
  const [trendGroupBy, setTrendGroupBy] = useState<"day" | "hour">("day");
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [widgetOrder, setWidgetOrder] = useState<WidgetKey[]>(["trend", "breakdown"]);
  const [isExporting, setIsExporting] = useState(false);

  const widgetOrderStorageKey = `dashboard-widget-order:${userId ?? "anon"}`;

  useEffect(() => {
    const saved = localStorage.getItem(widgetOrderStorageKey);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as WidgetKey[];
        if (Array.isArray(parsed) && parsed.length === 2) setWidgetOrder(parsed);
      } catch {
        // ignore malformed saved order, keep default
      }
    }
  }, [widgetOrderStorageKey]);

  function moveWidget(key: WidgetKey, direction: -1 | 1) {
    setWidgetOrder((prev) => {
      const index = prev.indexOf(key);
      const swapWith = index + direction;
      if (swapWith < 0 || swapWith >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[swapWith]] = [next[swapWith], next[index]];
      localStorage.setItem(widgetOrderStorageKey, JSON.stringify(next));
      return next;
    });
  }

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary", selectedStoreId],
    queryFn: () => getDashboardSummary(selectedStoreId ?? undefined),
  });

  const trendQuery = useQuery({
    queryKey: ["dashboard-trend", range, trendGroupBy, selectedStoreId],
    queryFn: () =>
      getDashboardTrend({
        date_from: range.dateFrom,
        date_to: range.dateTo,
        group_by: trendGroupBy,
        store_id: selectedStoreId ?? undefined,
      }),
    retry: (count, err) => isAxiosError(err) && err.response?.status !== 403 && count < 3,
  });

  const breakdownQuery = useQuery({
    queryKey: ["dashboard-breakdown", range, breakdownBy, selectedStoreId],
    queryFn: () =>
      getDashboardBreakdown({
        date_from: range.dateFrom,
        date_to: range.dateTo,
        by: breakdownBy,
        store_id: selectedStoreId ?? undefined,
      }),
    retry: (count, err) => isAxiosError(err) && err.response?.status !== 403 && count < 3,
  });

  const storesQuery = useQuery({
    queryKey: ["dashboard-stores", range],
    queryFn: () => getDashboardStores({ date_from: range.dateFrom, date_to: range.dateTo }),
    retry: (count, err) => isAxiosError(err) && err.response?.status !== 403 && count < 3,
  });

  const isRangeUpgradeRequired =
    trendQuery.isError && isAxiosError(trendQuery.error) && trendQuery.error.response?.status === 403;
  const isProMax = storesQuery.isSuccess;

  async function handleExportPdf() {
    setIsExporting(true);
    try {
      await downloadDashboardPdf({ date_from: range.dateFrom, date_to: range.dateTo });
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("dashboard.exportError")));
    } finally {
      setIsExporting(false);
    }
  }

  const summary = summaryQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("dashboard.title")}
        subtitle={t("dashboard.subtitle")}
        actions={
          isProMax ? (
            <Button variant="outline" onClick={() => void handleExportPdf()} isLoading={isExporting}>
              <Download className="h-4 w-4" />
              {t("dashboard.exportPdf")}
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label={t("dashboard.salesToday")}
          value={formatPaise(summary?.total_paise ?? 0)}
          icon={TrendingUp}
        />
        <StatTile label={t("dashboard.billsToday")} value={String(summary?.bill_count ?? 0)} icon={Receipt} />
        <StatTile
          label={t("dashboard.avgBillValue")}
          value={formatPaise(summary?.avg_bill_paise ?? 0)}
          icon={Receipt}
        />
        <StatTile
          label={t("dashboard.lowStockCount")}
          value={String(summary?.low_stock_count ?? 0)}
          icon={Boxes}
          action={
            <Link
              to="/stock/low-stock"
              className="flex items-center gap-0.5 text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              {t("dashboard.view")}
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
      </div>

      {summary && summary.top_items.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
          <p className="mb-3 text-sm font-medium text-slate-700">{t("dashboard.topItems")}</p>
          <ul className="flex flex-col divide-y divide-slate-100">
            {summary.top_items.map((item, i) => (
              <li key={item.name} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-700">
                  <span className="mr-2 text-slate-400">{i + 1}.</span>
                  {item.name}
                </span>
                <span className="font-medium text-slate-900">{formatPaise(item.revenue_paise)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isRangeUpgradeRequired ? (
        <EmptyState
          icon={Lock}
          title={t("dashboard.upgradeTitle")}
          description={t("dashboard.upgradeBody")}
          action={
            <Button asChild>
              <Link to="/settings/subscription">{t("dashboard.upgradeCta")}</Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <DateRangePicker value={range} onChange={setRange} />
            {isProMax && storesQuery.data && storesQuery.data.length > 1 && (
              <StoreTotalsTable
                data={storesQuery.data}
                selectedStoreId={selectedStoreId}
                onSelectStore={setSelectedStoreId}
              />
            )}
          </div>

          {widgetOrder.map((key, index) => (
            <div key={key} className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
              <div className="mb-3 flex items-center justify-between">
                {key === "trend" ? (
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-medium text-slate-700">{t("dashboard.salesTrend")}</p>
                    <div className="flex gap-1 rounded-lg border border-slate-200 p-0.5">
                      {(["day", "hour"] as const).map((g) => (
                        <button
                          key={g}
                          type="button"
                          onClick={() => setTrendGroupBy(g)}
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-medium",
                            trendGroupBy === g
                              ? "bg-brand-600 text-white"
                              : "text-slate-500 hover:bg-slate-100",
                          )}
                        >
                          {t(`dashboard.groupBy${g === "day" ? "Day" : "Hour"}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <p className="text-sm font-medium text-slate-700">{t("dashboard.breakdown")}</p>
                    <div className="flex gap-1 rounded-lg border border-slate-200 p-0.5">
                      {(["payment_mode", "category", "cashier"] as const).map((b) => (
                        <button
                          key={b}
                          type="button"
                          onClick={() => setBreakdownBy(b)}
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-medium",
                            breakdownBy === b
                              ? "bg-brand-600 text-white"
                              : "text-slate-500 hover:bg-slate-100",
                          )}
                        >
                          {t(`dashboard.breakdownBy.${b}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {isProMax && (
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => moveWidget(key, -1)}
                      disabled={index === 0}
                      className="flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-100 disabled:opacity-30"
                      aria-label={t("dashboard.moveUp")}
                    >
                      <ArrowUp className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveWidget(key, 1)}
                      disabled={index === widgetOrder.length - 1}
                      className="flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-100 disabled:opacity-30"
                      aria-label={t("dashboard.moveDown")}
                    >
                      <ArrowDown className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {key === "trend" ? (
                <SalesTrendChart data={trendQuery.data ?? []} groupBy={trendGroupBy} />
              ) : (
                <BreakdownChart data={breakdownQuery.data ?? []} />
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
