import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import { CustomerSelectorBar } from "@/modules/pos/CustomerSelectorBar";
import type { Order, PosSection } from "@/modules/pos/posApi";

// Result of picking a table or a customer slot: tapping a table in the picker always
// resolves immediately to "direct" (table selection no longer gates on open-order
// count — that's the CustomerSelectorBar's job, Phase 21). "resume"/"new-party" are
// produced by CustomerSelectorBar's chips instead: resume an existing customer's open
// order, or start a fresh one under that customer label.
export type TableSelection =
  | { kind: "direct"; sectionId: string; tableId: string | null }
  | { kind: "resume"; orderId: string }
  | { kind: "new-party"; sectionId: string; tableId: string; partyLabel: string };

// Shared by the table picker's (removed) party flow and CustomerSelectorBar's chips —
// resume the matching open order for this table+label if one exists, else start fresh.
export function resolveCustomerSlotSelection(
  table: Table,
  label: string,
  openOrders: Order[],
): TableSelection {
  const existing = openOrders.find((o) => o.table_id === table.id && o.party_label === label);
  return existing
    ? { kind: "resume", orderId: existing.id }
    : { kind: "new-party", sectionId: table.section_id, tableId: table.id, partyLabel: label };
}

interface TableWaiterBarProps {
  sections: PosSection[];
  tables: Table[];
  waiters: Waiter[];
  openOrders: Order[];
  sectionId: string;
  tableId: string | null;
  partyLabel: string | null;
  waiterId: string | null;
  waiterLocked: boolean;
  lockedWaiterName?: string;
  onSelectTable: (selection: TableSelection) => void;
  // Mandatory — the picker below only ever hands back a real waiter id, never null.
  onSelectWaiter: (waiterId: string) => void;
  // Controlled from the parent so the F10/F11 keyboard shortcuts (CLAUDE.md §9) can
  // open these pickers without duplicating open/close state in two places.
  openPicker: "table" | "waiter" | null;
  onOpenPickerChange: (picker: "table" | "waiter" | null) => void;
}

function TablePickerModal({
  sections,
  tables,
  openOrders,
  onSelect,
  onClose,
}: {
  sections: PosSection[];
  tables: Table[];
  openOrders: Order[];
  onSelect: (selection: TableSelection) => void;
  onClose: () => void;
}) {
  // A section with zero active tables (e.g. "Rooftop" not yet set up) has nothing to
  // pick, so it's dropped rather than shown as an always-empty dead end (POS-21).
  const seatingSections = sections
    .filter((s) => s.is_seating)
    .filter((s) => tables.some((t) => t.section_id === s.id && t.is_active));
  const nonSeatingSections = sections.filter((s) => !s.is_seating);

  // Every table tap resolves immediately — the Customer selector bar (rendered once a
  // table is chosen) is where resuming an existing customer's order or starting a new
  // one now happens, not this picker (Phase 21).
  function handleTableClick(section: PosSection, table: Table) {
    onSelect({ kind: "direct", sectionId: section.id, tableId: table.id });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-4 text-lg font-extrabold">🍽️ Select Table / Section</h2>

        {seatingSections.map((section) => {
          const sectionTables = tables.filter((t) => t.section_id === section.id && t.is_active);
          return (
            <div key={section.id} className="mb-4">
              <p className="mb-1.5 text-[11px] font-extrabold uppercase tracking-wider text-ink-faint">
                {section.name_en}
              </p>
              <div className="grid grid-cols-4 gap-2">
                {sectionTables.map((table) => {
                  const occupiedCount = openOrders.filter((o) => o.table_id === table.id).length;
                  return (
                    <button
                      key={table.id}
                      type="button"
                      onClick={() => handleTableClick(section, table)}
                      className={`relative rounded-lg border py-2.5 text-base font-extrabold transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent ${
                        occupiedCount > 0 ? "border-gold bg-gold-soft" : "border-border bg-surface-2"
                      }`}
                    >
                      {table.table_number}
                      {occupiedCount > 0 && (
                        <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-extrabold text-white">
                          {occupiedCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}

        {nonSeatingSections.length > 0 && (
          <div className="mb-2">
            <p className="mb-1.5 text-[11px] font-extrabold uppercase tracking-wider text-ink-faint">
              Other
            </p>
            <div className="flex flex-wrap gap-2">
              {nonSeatingSections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => onSelect({ kind: "direct", sectionId: section.id, tableId: null })}
                  className="rounded-full border border-border bg-surface-2 px-4 py-2 text-sm font-bold transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent"
                >
                  {section.name_en}
                </button>
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-3 w-full rounded-lg border border-border py-2 text-sm font-bold hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function WaiterPickerModal({
  waiters,
  onSelect,
  onClose,
}: {
  waiters: Waiter[];
  onSelect: (waiterId: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[85vh] w-full max-w-sm overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-4 text-lg font-extrabold">🧑‍🍳 Assign Waiter</h2>
        {/* No "Unassigned" option — waiter assignment is mandatory (production
            feedback), so this picker only ever hands back a real waiter id. */}
        <div className="flex flex-col gap-1.5">
          {waiters.filter((w) => w.is_active).length === 0 ? (
            <p className="px-1 py-2 text-sm text-ink-faint">
              No active waiters yet — a tenant_admin can add one in Waiter Master.
            </p>
          ) : (
            waiters
              .filter((w) => w.is_active)
              .map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => onSelect(w.id)}
                  className="rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-left text-sm font-bold hover:border-accent hover:bg-accent-soft hover:text-accent"
                >
                  {w.waiter_number} · {w.name}
                </button>
              ))
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-3 w-full rounded-lg border border-border py-2 text-sm font-bold hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export function TableWaiterBar({
  sections,
  tables,
  waiters,
  openOrders,
  sectionId,
  tableId,
  partyLabel,
  waiterId,
  waiterLocked,
  lockedWaiterName,
  onSelectTable,
  onSelectWaiter,
  openPicker: pickerOpen,
  onOpenPickerChange: setPickerOpen,
}: TableWaiterBarProps) {
  const currentSection = sections.find((s) => s.id === sectionId);
  const currentTable = tables.find((t) => t.id === tableId);
  const currentWaiter = waiters.find((w) => w.id === waiterId);

  return (
    // Table/customer/waiter selectors don't fit a phone-width screen side by side —
    // this scrolls horizontally instead of overlapping/clipping each other (found
    // during real-device testing), same pattern as the admin tables' overflow fix.
    // `shrink-0` on each child stops flex from squeezing them into an unreadable mess.
    <div className="flex items-center gap-2 overflow-x-auto border-b border-border bg-surface-2 px-4 py-2">
      <button
        type="button"
        onClick={() => setPickerOpen("table")}
        className="flex shrink-0 items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 transition-colors hover:border-accent"
      >
        <span>🍽️</span>
        <span className="text-xl font-black leading-none tracking-tight">
          {currentTable?.table_number ?? currentSection?.name_en ?? "Select"}
        </span>
        {currentTable && currentSection && (
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
            {currentSection.name_en}
          </span>
        )}
        {partyLabel && (
          <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-extrabold text-gold">
            {partyLabel}
          </span>
        )}
        <kbd className="ml-0.5 hidden rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[9px] font-bold text-ink-faint sm:inline">
          F10
        </kbd>
      </button>

      <CustomerSelectorBar
        table={currentTable ?? null}
        currentLabel={partyLabel}
        openOrders={openOrders}
        onSelect={onSelectTable}
      />

      <button
        type="button"
        onClick={() => !waiterLocked && setPickerOpen("waiter")}
        disabled={waiterLocked}
        className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-bold transition-colors disabled:cursor-default ${
          waiterLocked
            ? "border-gold bg-gold-soft text-gold opacity-90"
            : currentWaiter
              ? "border-gold bg-gold-soft text-gold"
              : "border-border bg-surface text-ink-soft hover:border-accent"
        }`}
      >
        <span>🧑‍🍳</span>
        {waiterLocked ? lockedWaiterName ?? "Me" : currentWaiter ? currentWaiter.name : "Assign Waiter"}
        {!waiterLocked && (
          <kbd className="ml-0.5 hidden rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[9px] font-bold text-ink-faint sm:inline">
            F11
          </kbd>
        )}
      </button>

      {pickerOpen === "table" && (
        <TablePickerModal
          sections={sections}
          tables={tables}
          openOrders={openOrders}
          onSelect={(selection) => {
            onSelectTable(selection);
            setPickerOpen(null);
          }}
          onClose={() => setPickerOpen(null)}
        />
      )}
      {pickerOpen === "waiter" && !waiterLocked && (
        <WaiterPickerModal
          waiters={waiters}
          onSelect={(w) => {
            onSelectWaiter(w);
            setPickerOpen(null);
          }}
          onClose={() => setPickerOpen(null)}
        />
      )}
    </div>
  );
}
