import { ChevronDown } from "lucide-react";
import { forwardRef, useId } from "react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, id, children, ...props }, ref) => {
    const generatedId = useId();
    const selectId = id ?? generatedId;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-sm font-medium text-slate-700">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            id={selectId}
            ref={ref}
            aria-invalid={Boolean(error)}
            className={cn(
              "h-11 w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 pr-9 text-base text-slate-900",
              "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
              "disabled:cursor-not-allowed disabled:bg-slate-50",
              error && "border-danger-500 focus:border-danger-500 focus:ring-danger-500/30",
              className,
            )}
            {...props}
          >
            {children}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>
        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    );
  },
);
Select.displayName = "Select";
