import { useTranslation } from "react-i18next";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { BreakdownRow } from "@/types/dashboard";
import { CATEGORICAL_COLORS, CHART_INK } from "@/utils/chartColors";
import { formatPaise, formatPaiseCompact } from "@/utils/money";

export interface BreakdownChartProps {
  data: BreakdownRow[];
}

/** Horizontal bar chart, one bar per category, colored in the fixed
 * categorical slot order. A visible legend row underneath supplements the
 * bars — required "relief" for the three slots (aqua/yellow/magenta) that
 * sit below 3:1 contrast against the surface (dataviz skill palette.md). */
export function BreakdownChart({ data }: BreakdownChartProps) {
  const { t } = useTranslation();

  if (data.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-400">{t("dashboard.noData")}</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <ResponsiveContainer width="100%" height={Math.max(140, data.length * 44)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 24, left: 0, bottom: 4 }}
          barCategoryGap={12}
        >
          <XAxis
            type="number"
            tickFormatter={(v: number) => formatPaiseCompact(v)}
            tick={{ fill: CHART_INK.muted, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: CHART_INK.axis }}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fill: CHART_INK.secondary, fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            width={110}
          />
          <Tooltip
            formatter={(value?: number | string | ReadonlyArray<number | string>) => [
              formatPaise(Number(Array.isArray(value) ? value[0] : value)),
              t("dashboard.sales"),
            ]}
            contentStyle={{ borderRadius: 8, border: `1px solid ${CHART_INK.grid}`, fontSize: 13 }}
          />
          <Bar dataKey="total_paise" radius={[0, 4, 4, 0]} maxBarSize={24}>
            {data.map((row, i) => (
              <Cell key={row.label} fill={CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-slate-100 pt-3 text-sm">
        {data.map((row, i) => (
          <div key={row.label} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length] }}
              aria-hidden="true"
            />
            <span className="text-slate-700">{row.label}</span>
            <span className="font-medium text-slate-900">{formatPaise(row.total_paise)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
