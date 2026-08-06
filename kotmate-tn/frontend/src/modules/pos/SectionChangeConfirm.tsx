import { formatINR } from "@/lib/utils";
import type { Order } from "@/modules/pos/posApi";

interface SectionChangeConfirmProps {
  currentSubtotal: number;
  preview: Order;
  onConfirm: () => void;
  onCancel: () => void;
}

// CLAUDE.md §9/Phase 07: switching a bill's table/section after items are already in
// the cart must recalculate and confirm new totals rather than silently changing them.
export function SectionChangeConfirm({
  currentSubtotal,
  preview,
  onConfirm,
  onCancel,
}: SectionChangeConfirmProps) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-2 text-lg font-extrabold text-gold">⚠️ Totals Will Change</h2>
        <p className="mb-3 text-sm text-ink-soft">
          Moving to <strong className="text-foreground">{preview.table_number ?? preview.section_name_en}</strong>{" "}
          ({preview.section_name_en}) changes item prices for this bill.
        </p>
        <div className="mb-4 flex items-center justify-between rounded-lg bg-surface-2 px-3.5 py-3 text-sm">
          <span className="tabular-nums font-semibold text-ink-faint">{formatINR(currentSubtotal)}</span>
          <span aria-hidden className="text-ink-faint">
            →
          </span>
          <span className="tabular-nums text-base font-extrabold">{formatINR(preview.subtotal)}</span>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-accent-foreground"
          >
            Apply New Totals
          </button>
        </div>
      </div>
    </div>
  );
}
