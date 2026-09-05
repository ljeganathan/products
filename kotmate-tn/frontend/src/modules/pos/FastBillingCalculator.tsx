import { forwardRef, useEffect, useImperativeHandle, useState } from "react";

import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import type { PosSection } from "@/modules/pos/posApi";
import type { TableSelection } from "@/modules/pos/TableWaiterBar";

type Slot = "table" | "waiter" | "item";
type ItemCodeResult = { ok: true; name: string } | { ok: false; error: string };

// Imperative handle so an external "pick from a list" UI (Guided POS's Fast Billing
// side search list) can add an item through the exact same path as typing its code
// and pressing Enter — same slot-unlocked guard, same added-items chip, same error
// display — instead of silently bypassing the calculator's own state.
export interface FastBillingCalculatorHandle {
  addItemByCode: (code: string) => void;
}

export interface FastBillingCalculatorProps {
  tables: Table[];
  waiters: Waiter[];
  // Takeaway/Online Delivery-style sections — no table_number to type a code against
  // (CLAUDE.md §9: "Non-seating sections skip table selection entirely"), so these are
  // offered as tap chips on the Table slot instead, same as the tap-based picker does.
  sections: PosSection[];
  // A `waiter` login is always locked to themself (TableWaiterBar's own waiterLocked) —
  // Fast Billing drops the Waiter slot entirely in that case rather than asking for a
  // code that has only one possible answer.
  waiterLocked: boolean;
  // Tenant-wide "Require waiter selection" setting, common to both POS layouts — when
  // false, the Waiter slot is skippable for a real table (matches Default/Guided POS's
  // main billing screens no longer hard-requiring one either).
  waiterMandatory: boolean;
  // Separate, narrower toggle scoped to non-seating selections (Takeaway/Online
  // Delivery) only — independent of waiterMandatory above.
  waiterMandatoryNonSeating: boolean;
  onSelectTable: (selection: TableSelection) => void | Promise<void>;
  onSelectWaiter: (waiterId: string) => void | Promise<void>;
  onAddItemByCode: (code: string) => Promise<ItemCodeResult>;
  // Called once every mandatory slot has resolved and the cashier is ready to move on
  // (either the "Done — Continue to Cart" button, or Cancel/Esc backing out).
  onDone: () => void;
}

const KEYPAD_DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

const keyClass =
  "flex h-12 items-center justify-center rounded-xl border border-border bg-surface-2 text-lg font-extrabold shadow-sm transition-colors active:bg-surface-3";

// Table/waiter "codes" are just whatever digits are on the laminated floor chart or
// staff sheet — table_number/waiter_number themselves are free-text ("T5", "W3", or
// just "5"), not a separate numeric-code field the way items have `item_code`. Matching
// on digits-only lets a cashier type the same short number regardless of which
// convention the admin used when setting up Table/Waiter Master.
function digitsOf(value: string): string {
  return value.replace(/\D/g, "");
}

function matchByCode<T extends { is_active: boolean }>(
  rows: T[],
  code: string,
  field: (row: T) => string,
): T[] {
  return rows.filter(
    (row) => row.is_active && (digitsOf(field(row)) === code || field(row).toLowerCase() === code.toLowerCase()),
  );
}

// Calculator-style single-screen entry for table + waiter + item codes — built for
// counters whose staff came from Tally/Marg/DOS-era billing machines and know their
// floor/waiter/item codes by heart (CLAUDE.md §9). One shared keypad feeds whichever
// slot is active; Enter resolves the current slot and auto-advances to the next, the
// same key-in-then-Enter rhythm those machines already trained into muscle memory.
// Item resolution/adding reuses the exact same backend lookup + stock/out-of-order
// checks the header's inline Code field and ItemCodeModal already use (`onAddItemByCode`)
// — this component only owns the table/waiter code matching, which has no server
// round-trip since `tables`/`waiters` are already loaded client-side. Shared by
// FastBillingModal (Default layout, wraps this in a popup) and Guided POS's
// FastBillingScreen (mounts this full-height, no popup chrome).
export const FastBillingCalculator = forwardRef<FastBillingCalculatorHandle, FastBillingCalculatorProps>(
  function FastBillingCalculator(
    {
      tables,
      waiters,
      sections,
      waiterLocked,
      waiterMandatory,
      waiterMandatoryNonSeating,
      onSelectTable,
      onSelectWaiter,
      onAddItemByCode,
      onDone,
    },
    ref,
  ) {
  const nonSeatingSections = sections.filter((s) => !s.is_seating);
  // Set once the Table slot resolves to a non-seating section (selectNonSeating below)
  // and never toggled back by anything else, matching how a real table pick's own
  // resolution is permanent for this component's lifetime too.
  const [pickedNonSeating, setPickedNonSeating] = useState(false);
  const skipWaiterSlot =
    waiterLocked || (pickedNonSeating ? !waiterMandatoryNonSeating : !waiterMandatory);
  const slots: Slot[] = skipWaiterSlot ? ["table", "item"] : ["table", "waiter", "item"];
  const [active, setActive] = useState<Slot>("table");
  const [tableCode, setTableCode] = useState("");
  const [waiterCode, setWaiterCode] = useState("");
  const [itemCode, setItemCode] = useState("");
  // Display-only label for whatever the Table slot resolved to — a table number ("T5")
  // or a non-seating section name ("Takeaway"); which one it is doesn't matter past this
  // point, `onSelectTable` already got the right `TableSelection` shape for either.
  const [resolvedPlaceLabel, setResolvedPlaceLabel] = useState<string | null>(null);
  const [resolvedWaiter, setResolvedWaiter] = useState<Waiter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [addedItems, setAddedItems] = useState<{ code: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);

  function valueFor(slot: Slot): string {
    return slot === "table" ? tableCode : slot === "waiter" ? waiterCode : itemCode;
  }
  function setValueFor(slot: Slot, v: string) {
    if (slot === "table") setTableCode(v);
    else if (slot === "waiter") setWaiterCode(v);
    else setItemCode(v);
  }

  // A slot can only become active once every slot before it has actually resolved — item
  // codes need a real table+waiter to add against, so this stops a stray tap/Tab from
  // landing on Item while Table is still blank (which would otherwise reach
  // `onAddItemByCode` while `readyToOrder` is false).
  function isSlotUnlocked(slot: Slot): boolean {
    if (slot === "table") return true;
    if (slot === "waiter") return !!resolvedPlaceLabel && !skipWaiterSlot;
    return !!resolvedPlaceLabel && (skipWaiterSlot || !!resolvedWaiter);
  }
  const unlockedSlots = slots.filter(isSlotUnlocked);

  function tapDigit(d: string) {
    setError(null);
    setValueFor(active, valueFor(active) + d);
  }
  function backspace() {
    setError(null);
    setValueFor(active, valueFor(active).slice(0, -1));
  }
  function clearActive() {
    setError(null);
    setValueFor(active, "");
  }
  function cycleNext() {
    setError(null);
    const idx = unlockedSlots.indexOf(active);
    setActive(unlockedSlots[(idx + 1) % unlockedSlots.length]);
  }
  function jumpTo(slot: Slot) {
    if (!isSlotUnlocked(slot)) return;
    setError(null);
    setActive(slot);
  }

  // Table/waiter apply to the real order immediately on resolving — the same "tap a
  // table, it's set" contract the picker modals already have, not deferred to a final
  // Done step. That's what lets the Item slot add straight into the live cart the moment
  // it's reached, rather than needing its own separate "now build the cart" phase.
  async function selectTable(table: Table) {
    setBusy(true);
    await onSelectTable({ kind: "direct", sectionId: table.section_id, tableId: table.id });
    setBusy(false);
    setError(null);
    setPickedNonSeating(false);
    setResolvedPlaceLabel(table.table_number);
    const idx = slots.indexOf("table");
    if (idx < slots.length - 1) setActive(slots[idx + 1]);
  }

  // Takeaway/Online Delivery — tapped directly rather than typed, since there's no
  // per-section numeric code (CLAUDE.md §9); same `TableSelection` shape as a table pick,
  // just with `tableId: null`. Always skips straight to the Item slot — non-seating
  // never has a Waiter slot to advance through, on any layout.
  async function selectNonSeating(section: PosSection) {
    setBusy(true);
    await onSelectTable({ kind: "direct", sectionId: section.id, tableId: null });
    setBusy(false);
    setError(null);
    setPickedNonSeating(true);
    setResolvedPlaceLabel(section.name_en);
    setTableCode("");
    setActive("item");
  }

  // Shared by typing a code + Enter (via confirmActive below) and any external
  // "pick from a list" entry point (FastBillingCalculatorHandle) — same slot-unlocked
  // guard, same added-items chip, same error display either way.
  async function addItemByCode(rawCode: string) {
    const code = rawCode.trim();
    if (!code || busy) return;
    if (!isSlotUnlocked("item")) {
      setError(skipWaiterSlot ? "Select a table first" : "Select a table and waiter first");
      return;
    }
    setActive("item");
    setError(null);
    setBusy(true);
    const result = await onAddItemByCode(code);
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setAddedItems((prev) => [...prev, { code, name: result.name }]);
    setItemCode("");
  }

  useImperativeHandle(ref, () => ({ addItemByCode: (code: string) => void addItemByCode(code) }));

  async function confirmActive() {
    const code = valueFor(active).trim();
    if (!code || busy) return;
    setError(null);

    if (active === "table") {
      const matches = matchByCode(tables, code, (t) => t.table_number);
      if (matches.length !== 1) {
        setError(
          matches.length === 0
            ? `No table with code ${code} — or tap Takeaway/Online Delivery below`
            : `More than one table matches ${code}`,
        );
        return;
      }
      await selectTable(matches[0]);
      return;
    }

    if (active === "waiter") {
      const matches = matchByCode(waiters, code, (w) => w.waiter_number);
      if (matches.length !== 1) {
        setError(matches.length === 0 ? `No waiter with code ${code}` : `More than one waiter matches ${code}`);
        return;
      }
      const waiter = matches[0];
      setBusy(true);
      await onSelectWaiter(waiter.id);
      setBusy(false);
      setResolvedWaiter(waiter);
      const idx = slots.indexOf("waiter");
      if (idx < slots.length - 1) setActive(slots[idx + 1]);
      return;
    }

    // Item slot — every earlier slot is already resolved (and already applied to the
    // real order above) by the time this is reachable, so table/waiter are set.
    await addItemByCode(code);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key >= "0" && e.key <= "9") {
        e.preventDefault();
        tapDigit(e.key);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        backspace();
      } else if (e.key === "Tab") {
        e.preventDefault();
        cycleNext();
      } else if (e.key === "Enter") {
        e.preventDefault();
        void confirmActive();
      } else if (e.key === "Escape") {
        onDone();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    active,
    tableCode,
    waiterCode,
    itemCode,
    tables,
    waiters,
    busy,
    resolvedPlaceLabel,
    resolvedWaiter,
    waiterLocked,
    waiterMandatory,
    waiterMandatoryNonSeating,
    pickedNonSeating,
  ]);

  const canFinish = !!resolvedPlaceLabel && (skipWaiterSlot || !!resolvedWaiter);

  return (
    <div>
      <h2 className="mb-1 text-lg font-extrabold">⚡ Fast Billing</h2>
      <p className="mb-3 text-xs text-ink-faint">
        Key in {skipWaiterSlot ? "table, then item" : "table, waiter, then item"} codes — Enter confirms
        and moves to the next field. No table code for Takeaway/Online Delivery — tap it instead.
      </p>

      <div className="mb-3 flex flex-col gap-1.5">
        <SlotRow
          icon="🍽️"
          label="Table"
          active={active === "table"}
          locked={false}
          value={tableCode}
          resolvedLabel={resolvedPlaceLabel}
          onClick={() => jumpTo("table")}
        />
        {active === "table" && nonSeatingSections.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-1">
            {nonSeatingSections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => void selectNonSeating(section)}
                disabled={busy}
                className="rounded-full border border-border bg-surface-2 px-3 py-1 text-[11px] font-bold text-ink-soft transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent disabled:opacity-40"
              >
                {section.name_en}
              </button>
            ))}
          </div>
        )}
        {!skipWaiterSlot && (
          <SlotRow
            icon="🧑‍🍳"
            label="Waiter"
            active={active === "waiter"}
            locked={!isSlotUnlocked("waiter")}
            value={waiterCode}
            resolvedLabel={resolvedWaiter?.name ?? null}
            onClick={() => jumpTo("waiter")}
          />
        )}
        <SlotRow
          icon="#️⃣"
          label="Item"
          active={active === "item"}
          locked={!isSlotUnlocked("item")}
          value={itemCode}
          resolvedLabel={null}
          onClick={() => jumpTo("item")}
        />
      </div>

      {error && <p className="mb-2 text-center text-xs font-semibold text-chili">{error}</p>}

      {addedItems.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {addedItems.map((it, i) => (
            <span
              key={`${it.code}-${i}`}
              className="rounded-full bg-surface-3 px-2.5 py-1 text-[11px] font-bold text-ink-soft"
            >
              {it.name}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        {KEYPAD_DIGITS.map((digit) => (
          <button key={digit} type="button" onClick={() => tapDigit(digit)} className={keyClass}>
            {digit}
          </button>
        ))}
        <button type="button" onClick={clearActive} className={`${keyClass} text-chili`} aria-label="Clear">
          C
        </button>
        <button type="button" onClick={() => tapDigit("0")} className={keyClass}>
          0
        </button>
        <button type="button" onClick={backspace} className={keyClass} aria-label="Backspace">
          ⌫
        </button>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2">
        <button type="button" onClick={cycleNext} className={`${keyClass} h-10 text-xs`}>
          ↹ Next Field
        </button>
        <button
          type="button"
          onClick={() => void confirmActive()}
          disabled={busy}
          className={`${keyClass} h-10 text-xs text-accent disabled:opacity-40`}
        >
          ↵ Enter
        </button>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onDone}
          disabled={!canFinish}
          className="flex-1 rounded-lg bg-accent py-2.5 text-sm font-extrabold text-accent-foreground disabled:opacity-40"
        >
          Done — Continue to Cart
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
    );
  },
);

function SlotRow({
  icon,
  label,
  active,
  locked,
  value,
  resolvedLabel,
  onClick,
}: {
  icon: string;
  label: string;
  active: boolean;
  locked: boolean;
  value: string;
  resolvedLabel: string | null;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={locked}
      className={`flex items-center gap-2.5 rounded-xl border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
        active ? "border-accent bg-accent-soft" : resolvedLabel ? "border-gold bg-gold-soft" : "border-border bg-surface-2"
      }`}
    >
      <span className="text-sm">{icon}</span>
      <span className="w-12 text-[9.5px] font-extrabold uppercase tracking-wide text-ink-faint">{label}</span>
      <span className="flex-1 font-mono text-lg font-extrabold tabular-nums">
        {value || <span className="text-sm font-semibold text-ink-faint">—</span>}
      </span>
      {resolvedLabel && <span className="text-xs font-bold text-gold">✓ {resolvedLabel}</span>}
    </button>
  );
}
