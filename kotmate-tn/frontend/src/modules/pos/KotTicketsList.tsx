import { useMemo } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ActiveKotTicket,
  type ActiveKotTicketItem,
  clearBilledKotTicket,
  listActiveKotTickets,
} from "@/modules/pos/kotApi";

interface KotTicketsListProps {
  onSelectOrder: (orderId: string) => void;
}

interface GroupedTicket {
  orderId: string;
  tableNumber: string | null;
  partyLabel: string | null;
  sectionNameEn: string;
  statuses: string[];
  tickets: ActiveKotTicket[];
  // True once any ticket in the group was created via Guided POS's combined
  // "KOT + Bill" action — its order is already billed, so this group's "Bill this
  // ticket" action is replaced by a plain status pill.
  billedViaKot: boolean;
  billNumber: string | null;
}

// A single table+customer can have multiple KOT tickets (repeat-KOT — add-on items sent
// in a later batch, CLAUDE.md §8), but they all belong to the same order and get billed
// together — so group by order_id into one row. Each ticket keeps its own item list and
// status rather than being flattened into one merged list, so the expanded view can show
// which items are at which kitchen status (new/preparing/ready) per ticket.
function groupTicketsByOrder(tickets: ActiveKotTicket[]): GroupedTicket[] {
  const byOrder = new Map<string, GroupedTicket>();
  for (const ticket of tickets) {
    let group = byOrder.get(ticket.order_id);
    if (!group) {
      group = {
        orderId: ticket.order_id,
        tableNumber: ticket.table_number,
        partyLabel: ticket.party_label,
        sectionNameEn: ticket.section_name_en,
        statuses: [],
        tickets: [],
        billedViaKot: false,
        billNumber: null,
      };
      byOrder.set(ticket.order_id, group);
    }
    if (!group.statuses.includes(ticket.status)) group.statuses.push(ticket.status);
    if (ticket.order_billed_via_kot) {
      group.billedViaKot = true;
      group.billNumber = ticket.bill_number ?? group.billNumber;
    }
    group.tickets.push(ticket);
  }
  return Array.from(byOrder.values());
}

// Presentational list shared by the Default layout's KotTicketsPopup (wraps this in a
// modal) and Guided POS's KotTicketsScreen (mounts this full-height, no modal chrome) —
// sourced from Phase 08's GET /api/v1/kot/tickets/active, every currently open ticket
// across the location, so a cashier can pick up an order a waiter already fired to the
// kitchen from a different device (CLAUDE.md §11).
export function KotTicketsList({ onSelectOrder }: KotTicketsListProps) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["kot-tickets-active"],
    queryFn: () => listActiveKotTickets(),
    retry: false,
  });
  const grouped = useMemo(() => (data ? groupTicketsByOrder(data) : undefined), [data]);

  // Dismisses every ticket in a "bill already printed" group — in practice always one
  // ticket (the combined KOT+Bill route only ever fires once per order), cleared in
  // parallel for correctness if that ever changes.
  const clearMutation = useMutation({
    mutationFn: (ticketIds: string[]) => Promise.all(ticketIds.map((id) => clearBilledKotTicket(id))),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["kot-tickets-active"] }),
  });

  return (
    <>
      {isLoading && <p className="text-sm text-ink-faint">Loading…</p>}
      {isError && (
        <p className="rounded-lg bg-surface-2 px-3.5 py-3 text-sm text-ink-soft">
          Couldn't load kitchen tickets right now — try again in a moment.
        </p>
      )}
      {grouped && grouped.length === 0 && (
        <p className="text-sm text-ink-faint">No open kitchen tickets right now.</p>
      )}
      {grouped && grouped.length > 0 && (
        <ul className="flex flex-col gap-2">
          {grouped.map((group) => (
            <li key={group.orderId} className="overflow-hidden rounded-lg border border-border bg-surface-2">
              <details>
                <summary className="flex cursor-pointer list-none flex-col gap-1 px-3.5 py-2.5 marker:content-none">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center">
                      <span className="text-lg font-black">{group.tableNumber ?? "—"}</span>
                      {group.partyLabel && (
                        <span className="ml-1.5 rounded-full bg-gold-soft px-1.5 py-0.5 text-[10px] font-extrabold text-gold">
                          {group.partyLabel}
                        </span>
                      )}
                      <span className="ml-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
                        {group.sectionNameEn}
                      </span>
                    </span>
                    <span className="text-xs font-semibold capitalize text-ink-faint">
                      {group.statuses.join(", ")}
                    </span>
                  </div>
                  <span className="font-mono text-xs text-ink-faint">
                    #{group.tickets.map((t) => t.ticket_number).join(", #")}
                  </span>
                </summary>
                <div className="border-t border-dashed border-border px-3.5 py-2">
                  <div className="mb-2 flex flex-col gap-2">
                    {group.tickets.map((ticket) => (
                      <div key={ticket.id} className="rounded-md bg-surface px-2.5 py-2">
                        <div className="mb-1 flex items-center justify-between">
                          <span className="font-mono text-[11px] font-bold text-ink-faint">
                            #{ticket.ticket_number}
                          </span>
                          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold capitalize text-accent">
                            {ticket.status}
                          </span>
                        </div>
                        <ul className="flex flex-col gap-0.5">
                          {ticket.items.map((item: ActiveKotTicketItem, i: number) => (
                            <li key={i} className="flex items-center justify-between text-xs">
                              <span>
                                {item.name_en}
                                {item.name_ta && <span className="ml-1.5 text-ink-faint">{item.name_ta}</span>}
                              </span>
                              <span className="font-bold">×{item.quantity}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                  {group.billedViaKot ? (
                    <div className="flex items-center gap-1.5">
                      <span className="flex-1 rounded-md bg-accent-soft py-1.5 text-center text-xs font-bold text-accent">
                        ✓ {group.billNumber ? `Bill #${group.billNumber} — ` : ""}Bill already printed
                      </span>
                      <button
                        type="button"
                        onClick={() => clearMutation.mutate(group.tickets.map((t) => t.id))}
                        disabled={clearMutation.isPending}
                        className="rounded-md border border-border px-2.5 py-1.5 text-xs font-bold text-ink-soft hover:border-chili hover:text-chili disabled:opacity-40"
                      >
                        Clear
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onSelectOrder(group.orderId)}
                      className="w-full rounded-md border border-accent bg-accent-soft py-1.5 text-xs font-bold text-accent hover:bg-accent hover:text-accent-foreground"
                    >
                      Bill this ticket
                    </button>
                  )}
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
