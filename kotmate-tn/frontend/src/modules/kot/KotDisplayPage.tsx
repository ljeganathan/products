import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listItems } from "@/modules/admin/itemsApi";
import { listLocations } from "@/modules/admin/locationsApi";
import { useAuthStore } from "@/modules/auth/authStore";
import { type ActiveKotTicket, listActiveKotTickets, updateKotTicketStatus } from "@/modules/pos/kotApi";
import { useLocationSocket } from "@/modules/realtime/useLocationSocket";

import { KotTicketCard } from "./KotTicketCard";

interface StockOverride {
  available_qty: number;
  low_stock: boolean;
  out_of_stock: boolean;
}

const COLUMNS: { status: ActiveKotTicket["status"]; label: string; accent: string }[] = [
  { status: "new", label: "New", accent: "text-ink-soft" },
  { status: "preparing", label: "Preparing", accent: "text-gold" },
  { status: "ready", label: "Ready", accent: "text-veg" },
];

// Kitchen Display View (Phase 08) — the `kitchen` ("KOT User") role's only screen
// (CLAUDE.md §5), so this renders standalone rather than inside AppShell's nav shell,
// same as POSPage does for pos_user/waiter.
export function KotDisplayPage() {
  const role = useAuthStore((s) => s.role)!;
  const queryClient = useQueryClient();
  const [stockOverrides, setStockOverrides] = useState<Record<string, StockOverride>>({});

  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const location = locations[0];

  const { data: tickets = [], isLoading } = useQuery({
    queryKey: ["kot-tickets-active"],
    queryFn: listActiveKotTickets,
    refetchInterval: 15_000,
  });

  const { data: items = [] } = useQuery({
    queryKey: ["kds-tracked-items"],
    queryFn: () => listItems(),
  });

  useLocationSocket(location?.id, (msg) => {
    if (msg.type === "kot_ticket") {
      void queryClient.invalidateQueries({ queryKey: ["kot-tickets-active"] });
    } else if (msg.type === "item_stock") {
      const itemId = msg.item_id as string;
      setStockOverrides((prev) => ({
        ...prev,
        [itemId]: {
          available_qty: msg.available_qty as number,
          low_stock: msg.low_stock as boolean,
          out_of_stock: msg.out_of_stock as boolean,
        },
      }));
    }
  });

  const advanceMutation = useMutation({
    mutationFn: ({ ticketId, status }: { ticketId: string; status: "preparing" | "ready" }) =>
      updateKotTicketStatus(ticketId, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["kot-tickets-active"] });
    },
  });

  const canAdvance = role === "kitchen" || role === "tenant_admin";

  // Low-stock banner (CLAUDE.md §11): tracked items whose live-merged available_qty has
  // dropped to ≤5, so kitchen staff can flag a shortage before it becomes a walked-back
  // promise at the table. Sourced from the full tracked-item list, not just what's on
  // currently open tickets — a shortage matters even before the next order for it comes in.
  const lowStockItems = items
    .filter((item) => item.track_inventory)
    .map((item) => {
      const override = stockOverrides[item.id];
      const availableQty = override ? override.available_qty : item.available_qty;
      return { ...item, availableQty };
    })
    .filter((item) => item.availableQty !== null && item.availableQty <= 5);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex items-center gap-2.5 border-b border-border bg-surface px-4 py-2.5 shadow-pos">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-emerald-900 text-[11px] font-extrabold text-accent-foreground">
          KM
        </span>
        <span className="text-[13px] font-extrabold leading-none">Kitchen Display</span>
      </header>

      {lowStockItems.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-chili-soft px-4 py-2">
          <span className="text-xs font-extrabold text-chili">⚠ Low stock:</span>
          {lowStockItems.map((item) => (
            <span key={item.id} className="rounded-full bg-surface px-2.5 py-1 text-xs font-bold text-chili">
              {item.name_en} — {item.availableQty === 0 ? "out" : `${item.availableQty} left`}
            </span>
          ))}
        </div>
      )}

      <main className="flex-1 overflow-y-auto p-4">
        {isLoading && <p className="text-sm text-ink-faint">Loading tickets…</p>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const columnTickets = tickets.filter((t) => t.status === col.status);
            return (
              <section key={col.status}>
                <h2 className={`mb-2 text-sm font-extrabold uppercase tracking-wide ${col.accent}`}>
                  {col.label}{" "}
                  <span className="text-ink-faint">
                    ({columnTickets.length})
                  </span>
                </h2>
                <ul className="flex flex-col gap-3">
                  {columnTickets.map((ticket) => (
                    <KotTicketCard
                      key={ticket.id}
                      ticket={ticket}
                      canAdvance={canAdvance}
                      advancing={advanceMutation.isPending}
                      onAdvance={(ticketId, nextStatus) =>
                        advanceMutation.mutate({ ticketId, status: nextStatus })
                      }
                    />
                  ))}
                  {columnTickets.length === 0 && (
                    <li className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-ink-faint">
                      No tickets
                    </li>
                  )}
                </ul>
              </section>
            );
          })}
        </div>
      </main>
    </div>
  );
}
