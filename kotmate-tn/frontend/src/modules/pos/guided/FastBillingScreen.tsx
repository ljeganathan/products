import { useRef, useState } from "react";

import { formatINR } from "@/lib/utils";
import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import { FastBillingCalculator, type FastBillingCalculatorHandle } from "@/modules/pos/FastBillingCalculator";
import type { PosItem, PosSection } from "@/modules/pos/posApi";
import type { TableSelection } from "@/modules/pos/TableWaiterBar";

type ItemCodeResult = { ok: true; name: string } | { ok: false; error: string };

interface FastBillingScreenProps {
  tables: Table[];
  waiters: Waiter[];
  sections: PosSection[];
  waiterLocked: boolean;
  waiterMandatory: boolean;
  waiterMandatoryNonSeating: boolean;
  allItems: PosItem[];
  onSelectTable: (selection: TableSelection) => void | Promise<void>;
  onSelectWaiter: (waiterId: string) => void | Promise<void>;
  onAddItemByCode: (code: string) => Promise<ItemCodeResult>;
  onDone: () => void;
}

// Full-screen version of the real FastBillingModal: the Table/Waiter/Item keypad
// calculator gets the bulk of the screen, matching the real modal's design exactly —
// the only new addition is this narrow, secondary side list (code + name, with a small
// search box) for staff who don't remember a code, kept deliberately limited-width so
// it never competes with the calculator for space.
export function FastBillingScreen({
  tables,
  waiters,
  sections,
  waiterLocked,
  waiterMandatory,
  waiterMandatoryNonSeating,
  allItems,
  onSelectTable,
  onSelectWaiter,
  onAddItemByCode,
  onDone,
}: FastBillingScreenProps) {
  const [search, setSearch] = useState("");
  const calculatorRef = useRef<FastBillingCalculatorHandle>(null);

  const codedItems = allItems.filter((i) => i.item_code);
  const filtered = search
    ? codedItems.filter(
        (i) =>
          i.name_en.toLowerCase().includes(search.toLowerCase()) ||
          (i.item_code ?? "").toLowerCase().includes(search.toLowerCase()),
      )
    : codedItems;

  // Routes through the calculator's own addItemByCode — same slot-unlocked guard,
  // same added-items chip, same error display as typing the code and pressing Enter,
  // rather than silently bypassing the calculator's own state.
  function handleRowClick(item: PosItem) {
    if (!item.item_code) return;
    calculatorRef.current?.addItemByCode(item.item_code);
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-1 justify-center overflow-y-auto p-6">
        <div className="w-full max-w-md">
          <FastBillingCalculator
            ref={calculatorRef}
            tables={tables}
            waiters={waiters}
            sections={sections}
            waiterLocked={waiterLocked}
            waiterMandatory={waiterMandatory}
            waiterMandatoryNonSeating={waiterMandatoryNonSeating}
            onSelectTable={onSelectTable}
            onSelectWaiter={onSelectWaiter}
            onAddItemByCode={onAddItemByCode}
            onDone={onDone}
          />
        </div>
      </div>

      <div className="flex w-[230px] flex-none flex-col border-l border-border bg-surface">
        <p className="px-3.5 pb-1.5 pt-3.5 text-[10.5px] font-extrabold uppercase tracking-wide text-ink-faint">
          Find item by name
        </p>
        <div className="px-3.5 pb-2.5">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search code or name…"
            className="w-full rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-xs font-semibold outline-none"
          />
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2.5">
          {filtered.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleRowClick(item)}
              className="flex w-full items-center gap-1.5 rounded-md px-1.5 py-1.5 text-left text-[11.5px] hover:bg-surface-2"
            >
              <span className="w-7 shrink-0 text-[10px] font-extrabold text-ink-faint">#{item.item_code}</span>
              <span className="min-w-0 flex-1 truncate font-bold">{item.name_en}</span>
              <span className="shrink-0 text-[10.5px] font-extrabold tabular-nums text-veg">
                {formatINR(item.price)}
              </span>
            </button>
          ))}
          {filtered.length === 0 && <p className="px-2 py-3 text-[11px] text-ink-faint">No items found</p>}
        </div>
      </div>
    </div>
  );
}
