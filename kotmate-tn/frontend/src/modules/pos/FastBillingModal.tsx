import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import { FastBillingCalculator } from "@/modules/pos/FastBillingCalculator";
import type { PosSection } from "@/modules/pos/posApi";
import type { TableSelection } from "@/modules/pos/TableWaiterBar";

type ItemCodeResult = { ok: true; name: string } | { ok: false; error: string };

interface FastBillingModalProps {
  tables: Table[];
  waiters: Waiter[];
  sections: PosSection[];
  waiterLocked: boolean;
  waiterMandatory: boolean;
  onSelectTable: (selection: TableSelection) => void | Promise<void>;
  onSelectWaiter: (waiterId: string) => void | Promise<void>;
  onAddItemByCode: (code: string) => Promise<ItemCodeResult>;
  onClose: () => void;
}

// Modal chrome around the shared FastBillingCalculator — reached from a "⚡ Fast
// Billing" button next to the table/waiter pickers in TableWaiterBar. Guided POS's
// FastBillingScreen mounts that same calculator full-height instead, with no popup
// wrapper, alongside an additional searchable item list.
export function FastBillingModal({
  tables,
  waiters,
  sections,
  waiterLocked,
  waiterMandatory,
  onSelectTable,
  onSelectWaiter,
  onAddItemByCode,
  onClose,
}: FastBillingModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-pos">
        <FastBillingCalculator
          tables={tables}
          waiters={waiters}
          sections={sections}
          waiterLocked={waiterLocked}
          waiterMandatory={waiterMandatory}
          onSelectTable={onSelectTable}
          onSelectWaiter={onSelectWaiter}
          onAddItemByCode={onAddItemByCode}
          onDone={onClose}
        />
      </div>
    </div>
  );
}
