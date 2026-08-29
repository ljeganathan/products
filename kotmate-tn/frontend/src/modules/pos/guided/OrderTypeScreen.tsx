import { useState } from "react";

import type { Table } from "@/modules/admin/tablesApi";
import type { Order, PosSection } from "@/modules/pos/posApi";

interface OrderTypeScreenProps {
  sections: PosSection[];
  tables: Table[];
  openOrders: Order[];
  onSelectTable: (table: Table) => void;
  onSelectNonSeating: (section: PosSection) => void;
}

// Order Type entry: Dine In (default-selected) vs. non-seating buttons as plain
// rectangles — driven off `sections` where `!is_seating`, so a future added
// non-seating section (e.g. "Drive-Through") appears automatically with no code
// change — then the square table grid, grouped by seating section, when Dine In is
// active. Tapping a non-seating button navigates straight to Item+Cart, no
// intermediate confirmation screen (round-1 feedback).
export function OrderTypeScreen({
  sections,
  tables,
  openOrders,
  onSelectTable,
  onSelectNonSeating,
}: OrderTypeScreenProps) {
  // Purely a display concern (which button renders as the solid-filled "selected"
  // chip) — tapping a non-seating button navigates away immediately, so this mostly
  // just keeps Dine In showing as selected, the documented default.
  const [activeType, setActiveType] = useState<string>("dinein");

  const seatingSections = sections
    .filter((s) => s.is_seating)
    .filter((s) => tables.some((t) => t.section_id === s.id && t.is_active));
  const nonSeatingSections = sections.filter((s) => !s.is_seating);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
        <p className="mb-2.5 text-[11px] font-extrabold uppercase tracking-wider text-ink-faint">Order type</p>
        <div className="mb-7 flex flex-wrap gap-2.5">
          <button
            type="button"
            onClick={() => setActiveType("dinein")}
            className={`rounded-2xl px-6 py-3 text-[14.5px] font-extrabold transition-colors ${
              activeType === "dinein"
                ? "bg-accent text-accent-foreground"
                : "border-2 border-border bg-surface text-ink-soft hover:border-accent"
            }`}
          >
            Dine In
          </button>
          {nonSeatingSections.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => {
                setActiveType(section.id);
                onSelectNonSeating(section);
              }}
              className={`rounded-2xl px-6 py-3 text-[14.5px] font-extrabold transition-colors ${
                activeType === section.id
                  ? "bg-veg text-accent-foreground"
                  : "border-2 border-veg bg-veg/15 text-veg hover:bg-veg/25"
              }`}
            >
              {section.name_en}
            </button>
          ))}
        </div>

        {activeType === "dinein" && (
          <>
            <p className="mb-2.5 text-[11px] font-extrabold uppercase tracking-wider text-ink-faint">
              Select table
            </p>
            <div className="flex flex-col gap-6">
              {seatingSections.map((section) => {
                const sectionTables = tables.filter((t) => t.section_id === section.id && t.is_active);
                return (
                  <div key={section.id}>
                    <p className="mb-2 text-xs font-extrabold uppercase tracking-wide text-ink-soft">
                      {section.name_en}
                    </p>
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(84px,1fr))] gap-2.5">
                      {sectionTables.map((table) => {
                        const occupiedCount = openOrders.filter((o) => o.table_id === table.id).length;
                        return (
                          <button
                            key={table.id}
                            type="button"
                            onClick={() => onSelectTable(table)}
                            className={`relative flex aspect-square flex-col items-center justify-center gap-0.5 rounded-2xl border-2 transition-colors ${
                              occupiedCount > 0
                                ? "border-gold bg-gold-soft"
                                : "border-border bg-surface hover:border-accent"
                            }`}
                          >
                            <span
                              className={`text-[22px] font-extrabold leading-none ${occupiedCount > 0 ? "text-gold" : ""}`}
                            >
                              {table.table_number}
                            </span>
                            <span className="text-[10px] font-bold text-ink-faint">
                              {table.seating_capacity ?? 4} seats
                            </span>
                            {occupiedCount > 0 && (
                              <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-extrabold text-white shadow-pos">
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
              {seatingSections.length === 0 && (
                <p className="text-sm text-ink-faint">No seating tables set up yet.</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
