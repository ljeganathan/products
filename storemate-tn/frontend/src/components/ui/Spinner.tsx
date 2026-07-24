import { Loader2 } from "lucide-react";

export function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Loader2 className="h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
      <span className="sr-only">Loading</span>
    </div>
  );
}
