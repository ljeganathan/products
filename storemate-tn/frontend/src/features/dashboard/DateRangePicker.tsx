import { useTranslation } from "react-i18next";

import { cn } from "@/utils/cn";

export interface DateRange {
  dateFrom: string;
  dateTo: string;
}

export interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Preset rows, per the dataviz skill's filter-control spec — a short list
 * rather than a full calendar picker. */
export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  const { t } = useTranslation();
  const presets: { key: string; label: string; range: DateRange }[] = [
    { key: "today", label: t("dashboard.rangeToday"), range: { dateFrom: today(), dateTo: today() } },
    {
      key: "7d",
      label: t("dashboard.range7d"),
      range: { dateFrom: isoDaysAgo(6), dateTo: today() },
    },
    {
      key: "30d",
      label: t("dashboard.range30d"),
      range: { dateFrom: isoDaysAgo(29), dateTo: today() },
    },
  ];

  return (
    <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
      {presets.map((p) => (
        <button
          key={p.key}
          type="button"
          onClick={() => onChange(p.range)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            value.dateFrom === p.range.dateFrom && value.dateTo === p.range.dateTo
              ? "bg-brand-600 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
