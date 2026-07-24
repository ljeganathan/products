import { forwardRef, useId } from "react";
import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const generatedId = useId();
    const textareaId = id ?? generatedId;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={textareaId} className="text-sm font-medium text-slate-700">
            {label}
          </label>
        )}
        <textarea
          id={textareaId}
          ref={ref}
          aria-invalid={Boolean(error)}
          className={cn(
            "min-h-[5.5rem] w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900",
            "placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2",
            "focus:ring-brand-500/30 disabled:cursor-not-allowed disabled:bg-slate-50",
            error && "border-danger-500 focus:border-danger-500 focus:ring-danger-500/30",
            className,
          )}
          {...props}
        />
        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";
