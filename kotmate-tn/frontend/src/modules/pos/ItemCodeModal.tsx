interface ItemCodeModalProps {
  itemCode: string;
  onItemCodeChange: (value: string) => void;
  itemCodeError: string | null;
  onSubmit: () => void;
  onClose: () => void;
}

const KEYPAD_DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

const keyClass =
  "flex h-14 items-center justify-center rounded-xl border border-border bg-surface-2 text-xl font-extrabold shadow-sm transition-colors active:bg-surface-3";

// Mobile/tablet-narrow counterpart of the header's always-visible inline item-code field
// (that one is `hidden` below the `md` breakpoint — no room for it in a phone-width
// header). Reached from the "⋮" menu so a cashier on a counter phone still gets the same
// numeric-code quick-add flow laminated-menu counters use (CLAUDE.md §9).
//
// Deliberately NOT a text `<input>` — a real input here pops the Android/iOS on-screen
// keyboard over roughly half the modal every time it's opened, which then fights this
// small popup for space and is slower to hit than large on-screen keys (production
// feedback: "think in the end user perspective"). Since a counter code is always
// numeric (§9's laminated-menu codes), a dedicated on-screen keypad avoids the OS
// keyboard entirely — the same pattern a calculator or PIN pad uses instead of a text
// field — and the "display" below the title is a plain `<div>`, never focusable, so
// nothing can ever trigger it. Stays open after each add (display clears, keypad stays)
// so a run of repeat-order codes can be entered back-to-back; "Done" closes it explicitly.
export function ItemCodeModal({
  itemCode,
  onItemCodeChange,
  itemCodeError,
  onSubmit,
  onClose,
}: ItemCodeModalProps) {
  function tapDigit(digit: string) {
    onItemCodeChange(itemCode + digit);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="w-full max-w-xs rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-1 text-lg font-extrabold">#️⃣ Item Code</h2>
        <p className="mb-3 text-xs text-ink-faint">
          Tap the item's counter code, then Add — stays open so you can add several in a row.
        </p>

        <div
          className={`mb-3 flex h-14 items-center justify-center rounded-xl border-2 bg-surface-2 text-3xl font-extrabold tabular-nums ${
            itemCodeError ? "border-chili" : "border-border"
          }`}
        >
          {itemCode || <span className="text-ink-faint">e.g. 301</span>}
        </div>
        {itemCodeError && (
          <p className="mb-3 text-center text-xs font-semibold text-chili">{itemCodeError}</p>
        )}

        <div className="grid grid-cols-3 gap-2">
          {KEYPAD_DIGITS.map((digit) => (
            <button key={digit} type="button" onClick={() => tapDigit(digit)} className={keyClass}>
              {digit}
            </button>
          ))}
          <button
            type="button"
            onClick={() => onItemCodeChange("")}
            className={`${keyClass} text-chili`}
            aria-label="Clear"
          >
            C
          </button>
          <button type="button" onClick={() => tapDigit("0")} className={keyClass}>
            0
          </button>
          <button
            type="button"
            onClick={() => onItemCodeChange(itemCode.slice(0, -1))}
            className={keyClass}
            aria-label="Backspace"
          >
            ⌫
          </button>
        </div>

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={onSubmit}
            disabled={!itemCode}
            className="flex-1 rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
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
