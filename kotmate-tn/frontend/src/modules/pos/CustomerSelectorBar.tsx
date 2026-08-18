import type { Table } from "@/modules/admin/tablesApi";
import { resolveCustomerSlotSelection, type TableSelection } from "@/modules/pos/TableWaiterBar";
import type { Order } from "@/modules/pos/posApi";

interface CustomerSelectorBarProps {
  table: Table | null;
  currentLabel: string | null;
  openOrders: Order[];
  onSelect: (selection: TableSelection) => void;
}

// Always-visible, capacity-bounded replacement for the old reactive "Party 1/Party 2"
// picker modal (Phase 21, formerly Phase 19's PartyPickerView). Only rendered once a
// seating table is selected — non-seating sections (Takeaway/Online Delivery) have no
// customer concept, consistent with `party_label`'s existing table_id-required
// constraint on the backend.
export function CustomerSelectorBar({ table, currentLabel, openOrders, onSelect }: CustomerSelectorBarProps) {
  if (!table) return null;
  const capacity = table.seating_capacity ?? 4;
  const labels = Array.from({ length: capacity }, (_, i) => `Customer-${i + 1}`);

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <span className="shrink-0 text-[10px] font-extrabold uppercase tracking-wide text-ink-faint">Customer</span>
      {labels.map((label) => {
        const occupiedOrder = openOrders.find((o) => o.table_id === table.id && o.party_label === label);
        const isActive = currentLabel === label;
        return (
          <button
            key={label}
            type="button"
            onClick={() => onSelect(resolveCustomerSlotSelection(table, label, openOrders))}
            className={`relative shrink-0 rounded-lg border px-3.5 py-2.5 text-sm font-bold transition-colors ${
              isActive
                ? "border-accent bg-accent-soft text-accent"
                : occupiedOrder
                  ? "border-gold bg-gold-soft text-gold"
                  : "border-border bg-surface text-ink-soft hover:border-accent"
            }`}
          >
            {label.replace("Customer-", "C")}
            {occupiedOrder && (
              <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-gold" aria-label="occupied" />
            )}
          </button>
        );
      })}
    </div>
  );
}
