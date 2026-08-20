import { useEffect, useRef } from "react";

interface ItemCodeModalProps {
  itemCode: string;
  onItemCodeChange: (value: string) => void;
  itemCodeError: string | null;
  onSubmit: (onDone?: (success: boolean) => void) => void;
  onClose: () => void;
}

// Mobile/tablet-narrow counterpart of the header's always-visible inline item-code field
// (that one is `hidden` below the `md` breakpoint — no room for it in a phone-width
// header). Reached from the "⋮" menu so a cashier on a counter phone still gets the same
// numeric-code quick-add flow laminated-menu-style counters use (CLAUDE.md §9). Stays
// open after each add — same auto-refocus-for-the-next-code behavior the desktop field
// already has — so a run of repeat-order codes can be entered back-to-back without
// reopening this modal each time; "Done" closes it explicitly.
export function ItemCodeModal({
  itemCode,
  onItemCodeChange,
  itemCodeError,
  onSubmit,
  onClose,
}: ItemCodeModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function refocus(success: boolean) {
    inputRef.current?.focus();
    if (!success) inputRef.current?.select();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="w-full max-w-xs rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-1 text-lg font-extrabold">#️⃣ Item Code</h2>
        <p className="mb-4 text-xs text-ink-faint">
          Enter the item's counter code and Add — stays open so you can add several in a row.
        </p>
        <input
          ref={inputRef}
          value={itemCode}
          onChange={(e) => onItemCodeChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onSubmit(refocus);
            }
          }}
          inputMode="numeric"
          placeholder="e.g. 301"
          className="w-full rounded-lg border border-border bg-surface-2 px-3 py-3 text-center text-2xl font-extrabold outline-none focus:border-accent"
        />
        {itemCodeError && (
          <p className="mt-2 text-center text-xs font-semibold text-chili">{itemCodeError}</p>
        )}
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => onSubmit(refocus)}
            className="flex-1 rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground"
          >
            + Add
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-surface-2"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
