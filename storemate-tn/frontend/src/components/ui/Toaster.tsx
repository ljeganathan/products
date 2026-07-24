import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useEffect } from "react";

import { useToastStore, type ToastMessage, type ToastVariant } from "@/store/toastStore";
import { cn } from "@/utils/cn";

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-success-200 bg-success-50 text-success-800",
  danger: "border-danger-200 bg-danger-50 text-danger-800",
  warning: "border-warning-200 bg-warning-50 text-warning-800",
  info: "border-info-200 bg-info-50 text-info-800",
};

const VARIANT_ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  danger: XCircle,
  warning: AlertTriangle,
  info: Info,
};

function ToastItem({ toast }: { toast: ToastMessage }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const Icon = VARIANT_ICONS[toast.variant];

  useEffect(() => {
    const timer = setTimeout(() => dismiss(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, dismiss]);

  return (
    <div
      role="alert"
      className={cn(
        "flex w-full max-w-sm items-start gap-3 rounded-xl border p-4 shadow-card-hover animate-in slide-in-from-bottom-2 fade-in",
        VARIANT_STYLES[toast.variant],
      )}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="text-sm font-medium">{toast.title}</p>
        {toast.description && <p className="mt-0.5 text-sm opacity-80">{toast.description}</p>}
      </div>
      <button
        type="button"
        onClick={() => dismiss(toast.id)}
        className="shrink-0 rounded p-1 hover:bg-black/5"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 sm:items-end sm:right-4 sm:left-auto"
    >
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto w-full sm:w-auto">
          <ToastItem toast={t} />
        </div>
      ))}
    </div>
  );
}
