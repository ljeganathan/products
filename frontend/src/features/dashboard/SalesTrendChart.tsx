import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TrendPoint } from "@/types/dashboard";
import { CHART_INK, SEQUENTIAL_BLUE, SEQUENTIAL_BLUE_FILL } from "@/utils/chartColors";
import { formatPaiseCompact } from "@/utils/money";

export interface SalesTrendChartProps {
  data: TrendPoint[];
  groupBy: "day" | "hour";
}

function formatBucket(bucket: string, groupBy: "day" | "hour"): string {
  const d = new Date(bucket);
  return groupBy === "hour"
    ? d.toLocaleTimeString("en-IN", { hour: "numeric" })
    : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function SalesTrendChart({ data, groupBy }: SalesTrendChartProps) {
  const { t } = useTranslation();
  const chartData = data.map((d) => ({ ...d, label: formatBucket(d.bucket, groupBy) }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={CHART_INK.grid} strokeDasharray="0" />
        <XAxis
          dataKey="label"
          stroke={CHART_INK.axis}
          tick={{ fill: CHART_INK.muted, fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: CHART_INK.axis }}
        />
        <YAxis
          stroke={CHART_INK.axis}
          tick={{ fill: CHART_INK.muted, fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => formatPaiseCompact(v)}
          width={64}
        />
        <Tooltip
          formatter={(value?: number | string | ReadonlyArray<number | string>) => [
            formatPaiseCompact(Number(Array.isArray(value) ? value[0] : value)),
            t("dashboard.sales"),
          ]}
          labelStyle={{ color: CHART_INK.primary }}
          contentStyle={{
            borderRadius: 8,
            border: `1px solid ${CHART_INK.grid}`,
            fontSize: 13,
          }}
        />
        <Area
          type="monotone"
          dataKey="total_paise"
          stroke={SEQUENTIAL_BLUE}
          strokeWidth={2}
          fill={SEQUENTIAL_BLUE_FILL}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
