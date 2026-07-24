import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface StatTileProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  action?: ReactNode;
}

/** Stat-tile contract per the dataviz skill: sentence-case label, no
 * trailing colon; Sans semibold value; optional trailing action (e.g. the
 * low-stock count's "View" link). */
export function StatTile({ label, value, icon: Icon, action }: StatTileProps) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 shadow-card">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
        <span>{label}</span>
      </div>
      <div className="flex items-end justify-between gap-2">
        <p className="text-2xl font-semibold text-slate-900">{value}</p>
        {action}
      </div>
    </div>
  );
}
