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
 * rather than a full calendar picker — plus explicit From/To inputs for a
 * custom range the presets don't cover. */
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
  const isCustomRange = !presets.some(
    (p) => p.range.dateFrom === value.dateFrom && p.range.dateTo === value.dateTo,
  );

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
        {presets.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => onChange(p.range)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              !isCustomRange && value.dateFrom === p.range.dateFrom && value.dateTo === p.range.dateTo
                ? "bg-brand-600 text-white"
                : "text-slate-600 hover:bg-slate-100",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1">
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          {t("dashboard.rangeFrom")}
          <input
            type="date"
            value={value.dateFrom}
            max={value.dateTo}
            onChange={(e) => e.target.value && onChange({ dateFrom: e.target.value, dateTo: value.dateTo })}
            className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
          />
        </label>
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          {t("dashboard.rangeTo")}
          <input
            type="date"
            value={value.dateTo}
            min={value.dateFrom}
            max={today()}
            onChange={(e) => e.target.value && onChange({ dateFrom: value.dateFrom, dateTo: e.target.value })}
            className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
          />
        </label>
      </div>
    </div>
  );
}
