import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { formatINR } from "@/lib/utils";
import { listOrders } from "@/modules/pos/posApi";

interface RecallListProps {
  locationId: string;
  onSelectOrder: (orderId: string) => void;
}

// Presentational list shared by the Default layout's RecallPanel (wraps this in a
// modal) and Guided POS's RecallScreen (mounts this full-height, no modal chrome).
export function RecallList({ locationId, onSelectOrder }: RecallListProps) {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["held-orders", locationId],
    queryFn: () => listOrders({ status: "held", location_id: locationId }),
  });

  const filtered = (data ?? []).filter((o) => {
    if (!search) return true;
    const haystack = `${o.table_number ?? ""} ${o.section_name_en} ${o.hold_label ?? ""}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  return (
    <>
      <input
        placeholder="Search table, section, or label…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-3 min-h-10 w-full rounded-lg border border-border bg-surface-2 px-3 text-sm outline-none focus:ring-2 focus:ring-accent"
      />

      {isLoading && <p className="text-sm text-ink-faint">Loading…</p>}
      {!isLoading && filtered.length === 0 && <p className="text-sm text-ink-faint">No held bills.</p>}
      <ul className="flex flex-col gap-2">
        {filtered.map((order) => (
          <li key={order.id}>
            <button
              type="button"
              onClick={() => onSelectOrder(order.id)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-surface-2 px-3.5 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent-soft"
            >
              <span>
                <span className="text-lg font-black">{order.table_number ?? "—"}</span>
                <span className="ml-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
                  {order.section_name_en}
                </span>
                {order.hold_label && <span className="ml-2 text-xs text-ink-faint">{order.hold_label}</span>}
              </span>
              <span className="tabular-nums text-sm font-extrabold">{formatINR(order.subtotal)}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
