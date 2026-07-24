import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { PlanMix } from "@/types/platformDashboard";
import { PLAN_TIER_COLORS } from "@/utils/chartColors";

export interface PlanMixChartProps {
  data: PlanMix[];
}

/** Plan tier is a fixed, brand-meaningful category already color-coded
 * across the console (Badge.tsx) — reused here rather than the generic
 * categorical palette, see utils/chartColors.ts. */
export function PlanMixChart({ data }: PlanMixChartProps) {
  const chartData = data.map((d) => ({ name: d.plan_name, code: d.plan_code, value: d.tenant_count }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="value"
          nameKey="name"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          strokeWidth={2}
          stroke="#fcfcfb"
        >
          {chartData.map((row) => (
            <Cell key={row.code} fill={PLAN_TIER_COLORS[row.code] ?? "#898781"} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ borderRadius: 8, fontSize: 13 }} />
        <Legend verticalAlign="bottom" height={32} />
      </PieChart>
    </ResponsiveContainer>
  );
}
