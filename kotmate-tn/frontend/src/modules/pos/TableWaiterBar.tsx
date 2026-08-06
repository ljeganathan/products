import type { Table } from "@/modules/admin/tablesApi";
import type { Waiter } from "@/modules/admin/waitersApi";
import type { PosSection } from "@/modules/pos/posApi";

interface TableWaiterBarProps {
  sections: PosSection[];
  tables: Table[];
  waiters: Waiter[];
  sectionId: string;
  tableId: string | null;
  waiterId: string | null;
  waiterLocked: boolean;
  lockedWaiterName?: string;
  onSelectTable: (sectionId: string, tableId: string | null) => void;
  onSelectWaiter: (waiterId: string | null) => void;
  // Controlled from the parent so the F10/F11 keyboard shortcuts (CLAUDE.md §9) can
  // open these pickers without duplicating open/close state in two places.
  openPicker: "table" | "waiter" | null;
  onOpenPickerChange: (picker: "table" | "waiter" | null) => void;
}

function TablePickerModal({
  sections,
  tables,
  onSelect,
  onClose,
}: {
  sections: PosSection[];
  tables: Table[];
  onSelect: (sectionId: string, tableId: string | null) => void;
  onClose: () => void;
}) {
  const seatingSections = sections.filter((s) => s.is_seating);
  const nonSeatingSections = sections.filter((s) => !s.is_seating);

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
              {sectionTables.length === 0 ? (
                <p className="text-xs text-ink-faint">No tables in this section</p>
              ) : (
                <div className="grid grid-cols-4 gap-2">
                  {sectionTables.map((table) => (
                    <button
                      key={table.id}
                      type="button"
                      onClick={() => onSelect(section.id, table.id)}
                      className="rounded-lg border border-border bg-surface-2 py-2.5 text-base font-extrabold transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent"
                    >
                      {table.table_number}
                    </button>
                  ))}
                </div>
              )}
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
                  onClick={() => onSelect(section.id, null)}
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
  sectionId,
  tableId,
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
          onSelect={(sec, tbl) => {
            onSelectTable(sec, tbl);
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
