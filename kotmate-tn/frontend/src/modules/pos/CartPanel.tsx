import { formatINR } from "@/lib/utils";
import type { Role } from "@/modules/auth/authStore";
import type { Order } from "@/modules/pos/posApi";

interface CartPanelProps {
  order: Order | null;
  role: Role;
  syncState: "idle" | "saving" | "saved" | "error";
  onQuantityChange: (lineId: string, newQty: number) => void;
  onHold: () => void;
  onSendKot: () => void;
  onBill: () => void;
  onClear: () => void;
  kotSending: boolean;
  showSyncIndicator?: boolean;
  // KOT screen is Pro Max only (production feedback round 2) — Lite/Pro tenants skip
  // the KOT step entirely and bill items directly.
  kdsEnabled: boolean;
  // Guided POS's non-seating orders relabel these two actions ("KOT + Print Bill" /
  // "Bill Only (No KOT)") since sending to KOT there also finalizes the bill in the
  // same action — everything else about this panel (line items, hold, role gating)
  // stays identical. Defaults preserve Default layout's exact existing copy.
  kotLabel?: string;
  billLabel?: string;
  // Guided POS has no keyboard shortcuts (round-2 feedback: "no need to show the hot
  // keys in any buttons") — Default layout keeps showing them (default false/undefined).
  hideHotkeyHints?: boolean;
}

export function CartPanel({
  order,
  role,
  syncState,
  onQuantityChange,
  onHold,
  onSendKot,
  onBill,
  onClear,
  kotSending,
  showSyncIndicator,
  kdsEnabled,
  kotLabel,
  billLabel,
  hideHotkeyHints,
}: CartPanelProps) {
  const canBill = role === "pos_user" || role === "tenant_admin" || role === "pos_operator";
  const isEmpty = !order || order.items.length === 0;
  const itemTally = order?.items.reduce((sum, l) => sum + l.quantity, 0) ?? 0;

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex-none border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <h2 className="text-[13px] font-extrabold uppercase tracking-wide text-ink-soft">
              Current Order
            </h2>
            {itemTally > 0 && (
              <span className="text-[11px] font-semibold text-ink-faint">
                {itemTally} item{itemTally !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {showSyncIndicator && syncState !== "idle" && (
              <span
                className={`text-[10px] font-extrabold ${
                  syncState === "error" ? "text-chili" : syncState === "saving" ? "text-gold" : "text-veg"
                }`}
              >
                {syncState === "saving" ? "Saving…" : syncState === "saved" ? "Saved" : "Sync failed"}
              </span>
            )}
            {!isEmpty && (
              <button
                type="button"
                onClick={onClear}
                className="rounded-md border border-border px-2 py-0.5 text-[10.5px] font-extrabold text-ink-soft hover:border-chili hover:text-chili"
                title="Clear cart (Esc)"
              >
                ✕ Clear
              </button>
            )}
          </div>
        </div>

        {/* Table number is the dominant visual anchor everywhere (CLAUDE.md §9) —
            bigger/bolder than item names, section is a smaller badge alongside it. */}
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <span className="text-[22px] font-black leading-none tracking-tight">
            {order?.table_number ?? (order ? order.section_name_en : "—")}
          </span>
          {order?.table_number && (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
              {order.section_name_en}
            </span>
          )}
          {order?.party_label && (
            <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-extrabold text-gold">
              👤 {order.party_label}
            </span>
          )}
          {order?.waiter_name && (
            <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[11px] font-bold text-gold">
              🧑‍🍳 {order.waiter_name}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-1">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 text-center text-ink-faint">
            <span className="text-3xl">🛒</span>
            <p className="text-sm font-medium">Cart is empty</p>
            <p className="text-xs">Add items to begin</p>
          </div>
        ) : (
          <ul>
            {order!.items.map((line) => {
              const outOfStock =
                line.track_inventory && line.available_qty !== null && line.available_qty <= 0;
              return (
                <li
                  key={line.id ?? `${line.item_id}-${line.notes ?? ""}`}
                  className="flex items-start gap-2 border-b border-dashed border-border py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-bold leading-tight">
                      {line.name_en}
                      {/* Two lines for the same item are now possible — one already fired
                          to the kitchen, one not (an add-on ordered after the first KOT
                          send) — so a sent line is labeled to explain why it's separate
                          from an adjacent unsent one for the same item. */}
                      {line.is_kot_sent && (
                        <span className="ml-1.5 rounded-full bg-gold-soft px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-gold">
                          Sent
                        </span>
                      )}
                    </p>
                    {line.name_ta && (
                      <p className="truncate text-xs font-medium leading-tight text-ink-soft">
                        {line.name_ta}
                      </p>
                    )}
                    <p className="tabular-nums text-[11px] text-ink-faint">{formatINR(line.unit_price)} each</p>
                    {outOfStock && (
                      <p className="text-[11px] font-bold text-chili">Now out of stock</p>
                    )}
                  </div>
                  <div className="flex items-center overflow-hidden rounded-lg border border-border">
                    <button
                      type="button"
                      onClick={() => line.id && onQuantityChange(line.id, line.quantity - 1)}
                      className="flex h-10 w-10 items-center justify-center bg-surface-2 text-base font-extrabold hover:bg-surface-3"
                      aria-label={`Decrease ${line.name_en}`}
                    >
                      −
                    </button>
                    <span className="tabular-nums w-8 text-center text-sm font-bold">{line.quantity}</span>
                    <button
                      type="button"
                      onClick={() => line.id && onQuantityChange(line.id, line.quantity + 1)}
                      disabled={outOfStock}
                      className="flex h-10 w-10 items-center justify-center bg-surface-2 text-base font-extrabold hover:bg-surface-3 disabled:opacity-40"
                      aria-label={`Increase ${line.name_en}`}
                    >
                      +
                    </button>
                  </div>
                  <span className="tabular-nums w-16 shrink-0 text-right text-[13px] font-extrabold">
                    {formatINR(line.line_total)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="flex-none">
        <div className="mx-3 mt-1 overflow-hidden rounded-xl border border-border bg-surface-2">
          <div className="border-b border-dashed border-border px-3.5 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-ink-faint">
            🧾 Bill Summary
          </div>
          <div className="px-3.5 py-2 text-[13px]">
            <div className="flex items-center justify-between py-0.5 text-ink-soft">
              <span>Subtotal</span>
              <span className="tabular-nums font-bold text-foreground">{formatINR(order?.subtotal ?? 0)}</span>
            </div>
          </div>
        </div>

        <div className="px-3 pb-3 pt-2.5">
          <div className={`grid gap-1.5 ${kdsEnabled ? "grid-cols-2" : "grid-cols-1"}`}>
            <button
              type="button"
              onClick={onHold}
              disabled={isEmpty}
              className="flex min-h-[34px] items-center justify-center gap-1.5 rounded-lg border border-border bg-surface-2 text-[12px] font-extrabold hover:border-ink-faint disabled:opacity-40"
            >
              ⏸ Hold{" "}
              {!hideHotkeyHints && <span className="text-[9.5px] font-bold opacity-60">Ctrl H</span>}
            </button>
            {kdsEnabled && (
              <button
                type="button"
                onClick={onSendKot}
                disabled={isEmpty || kotSending}
                className="flex min-h-[34px] items-center justify-center gap-1.5 rounded-lg border border-gold bg-gold-soft text-[12px] font-extrabold text-gold disabled:opacity-40"
              >
                {kotSending ? "Sending…" : (kotLabel ?? "🍳 Add to KOT")}
                {!kotSending && !kotLabel && !hideHotkeyHints && (
                  <span className="text-[9.5px] font-bold opacity-60">Ctrl ⏎</span>
                )}
              </button>
            )}
          </div>

          {canBill && (
            <button
              type="button"
              onClick={onBill}
              disabled={isEmpty}
              className="mt-2 flex min-h-[38px] w-full items-center justify-center gap-1.5 rounded-lg bg-accent text-sm font-extrabold text-accent-foreground disabled:opacity-40"
            >
              {billLabel ?? "🧾 Bill"}
              {!billLabel && !hideHotkeyHints && (
                <span className="text-[9.5px] font-bold opacity-75">Ctrl P</span>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
