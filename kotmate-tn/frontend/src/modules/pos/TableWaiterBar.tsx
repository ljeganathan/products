import { useState } from "react";

import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import type { Order, PosSection } from "@/modules/pos/posApi";

// Result of the table picker (Phase 19, POS-22): a table with no open orders resolves
// immediately to "direct" (unchanged pre-Phase-19 behaviour); an occupied table offers
// a party sub-picker resolving to either "resume" an existing party's order or start a
// genuinely new "new-party" order alongside it.
export type TableSelection =
  | { kind: "direct"; sectionId: string; tableId: string | null }
  | { kind: "resume"; orderId: string }
  | { kind: "new-party"; sectionId: string; tableId: string; partyLabel: string };

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
  onSelectWaiter: (waiterId: string | null) => void;
  // Controlled from the parent so the F10/F11 keyboard shortcuts (CLAUDE.md §9) can
  // open these pickers without duplicating open/close state in two places.
  openPicker: "table" | "waiter" | null;
  onOpenPickerChange: (picker: "table" | "waiter" | null) => void;
}

function PartyPickerView({
  table,
  section,
  openOrdersForTable,
  onSelect,
  onBack,
}: {
  table: Table;
  section: PosSection;
  openOrdersForTable: Order[];
  onSelect: (selection: TableSelection) => void;
  onBack: () => void;
}) {
  // max-existing-number + 1 rather than count + 1: parties don't always bill out in
  // arrival order (e.g. Party 1 leaves first), so counting remaining open orders can
  // regenerate a label ("Party 2") that's still in use by the party that's still open.
  const existingNumbers = openOrdersForTable
    .map((o) => /^Party (\d+)$/.exec(o.party_label ?? "")?.[1])
    .filter((n): n is string => !!n)
    .map(Number);
  const nextPartyNumber =
    existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : openOrdersForTable.length + 1;
  return (
    <div>
      <button type="button" onClick={onBack} className="mb-3 text-xs font-bold text-accent hover:underline">
        ← Back
      </button>
      <p className="mb-3 text-sm text-ink-soft">
        <span className="text-lg font-black">{table.table_number}</span>{" "}
        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
          {section.name_en}
        </span>{" "}
        already has {openOrdersForTable.length} open{" "}
        {openOrdersForTable.length === 1 ? "party" : "parties"} — pick one to continue, or start another.
      </p>
      <div className="flex flex-col gap-1.5">
        {openOrdersForTable.map((order, i) => (
          <button
            key={order.id}
            type="button"
            onClick={() => onSelect({ kind: "resume", orderId: order.id })}
            className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3.5 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent"
          >
            <span className="font-bold">{order.party_label ?? `Party ${i + 1}`}</span>
            <span className="text-xs text-ink-faint">
              {order.items.length} item{order.items.length === 1 ? "" : "s"}
            </span>
          </button>
        ))}
        <button
          type="button"
          onClick={() =>
            onSelect({
              kind: "new-party",
              sectionId: section.id,
              tableId: table.id,
              partyLabel: `Party ${nextPartyNumber}`,
            })
          }
          className="rounded-lg border border-dashed border-accent px-3.5 py-2.5 text-left text-sm font-bold text-accent hover:bg-accent-soft"
        >
          + New Party (Party {nextPartyNumber})
        </button>
      </div>
    </div>
  );
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
  const [partyPickerTable, setPartyPickerTable] = useState<Table | null>(null);

  // A section with zero active tables (e.g. "Rooftop" not yet set up) has nothing to
  // pick, so it's dropped rather than shown as an always-empty dead end (POS-21).
  const seatingSections = sections
    .filter((s) => s.is_seating)
    .filter((s) => tables.some((t) => t.section_id === s.id && t.is_active));
  const nonSeatingSections = sections.filter((s) => !s.is_seating);

  function handleTableClick(section: PosSection, table: Table) {
    const existing = openOrders.filter((o) => o.table_id === table.id);
    if (existing.length === 0) {
      onSelect({ kind: "direct", sectionId: section.id, tableId: table.id });
      return;
    }
    setPartyPickerTable(table);
  }

  const partyPickerSection =
    partyPickerTable && sections.find((s) => s.id === partyPickerTable.section_id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        {partyPickerTable && partyPickerSection ? (
          <PartyPickerView
            table={partyPickerTable}
            section={partyPickerSection}
            openOrdersForTable={openOrders.filter((o) => o.table_id === partyPickerTable.id)}
            onSelect={onSelect}
            onBack={() => setPartyPickerTable(null)}
          />
        ) : (
          <>
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
                            occupiedCount > 0
                              ? "border-gold bg-gold-soft"
                              : "border-border bg-surface-2"
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
          </>
        )}
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
  onSelect: (waiterId: string | null) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[85vh] w-full max-w-sm overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-4 text-lg font-extrabold">🧑‍🍳 Assign Waiter</h2>
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-left text-sm font-bold hover:border-accent hover:bg-accent-soft hover:text-accent"
          >
            Unassigned
          </button>
          {waiters
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
            ))}
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
    <div className="flex items-center gap-2 border-b border-border bg-surface-2 px-4 py-2">
      <button
        type="button"
        onClick={() => setPickerOpen("table")}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 transition-colors hover:border-accent"
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

      <button
        type="button"
        onClick={() => !waiterLocked && setPickerOpen("waiter")}
        disabled={waiterLocked}
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-bold transition-colors disabled:cursor-default ${
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
