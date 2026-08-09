import { useMemo } from "react";

import { useQuery } from "@tanstack/react-query";

import { type ActiveKotTicket, type ActiveKotTicketItem, listActiveKotTickets } from "@/modules/pos/kotApi";

interface KotTicketsPopupProps {
  onSelectOrder: (orderId: string) => void;
  onClose: () => void;
}

interface GroupedTicket {
  orderId: string;
  ticketNumbers: string[];
  tableNumber: string | null;
  partyLabel: string | null;
  sectionNameEn: string;
  statuses: string[];
  items: ActiveKotTicketItem[];
}

// A single table+customer can have multiple KOT tickets (repeat-KOT — add-on items sent
// in a later batch, CLAUDE.md §8), but they all belong to the same order and get billed
// together — so group by order_id into one row, merging item lines (same item across
// tickets combines into one quantity) rather than listing each physical ticket separately.
function groupTicketsByOrder(tickets: ActiveKotTicket[]): GroupedTicket[] {
  const byOrder = new Map<string, GroupedTicket>();
  for (const ticket of tickets) {
    let group = byOrder.get(ticket.order_id);
    if (!group) {
      group = {
        orderId: ticket.order_id,
        ticketNumbers: [],
        tableNumber: ticket.table_number,
        partyLabel: ticket.party_label,
        sectionNameEn: ticket.section_name_en,
        statuses: [],
        items: [],
      };
      byOrder.set(ticket.order_id, group);
    }
    group.ticketNumbers.push(ticket.ticket_number);
    if (!group.statuses.includes(ticket.status)) group.statuses.push(ticket.status);
    for (const item of ticket.items) {
      const existing = group.items.find((i) => i.name_en === item.name_en && i.name_ta === item.name_ta);
      if (existing) existing.quantity += item.quantity;
      else group.items.push({ ...item });
    }
  }
  return Array.from(byOrder.values());
}

// Sourced from Phase 08's GET /api/v1/kot/tickets/active — every currently open ticket
// across the location, so a cashier can pick up an order a waiter already fired to the
// kitchen from a different device (CLAUDE.md §11).
export function KotTicketsPopup({ onSelectOrder, onClose }: KotTicketsPopupProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["kot-tickets-active"],
    queryFn: listActiveKotTickets,
    retry: false,
  });
  const grouped = useMemo(() => (data ? groupTicketsByOrder(data) : undefined), [data]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-1 text-lg font-extrabold">🍳 KOT Tickets</h2>
        <p className="mb-4 text-xs text-ink-faint">
          Open kitchen tickets from any device — select one to bill it here.
        </p>

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
                  <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 marker:content-none">
                    <span>
                      <span className="font-mono text-xs text-ink-faint">
                        #{group.ticketNumbers.join(", #")}
                      </span>
                      <span className="ml-2 text-lg font-black">{group.tableNumber ?? "—"}</span>
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
                  </summary>
                  <div className="border-t border-dashed border-border px-3.5 py-2">
                    <ul className="mb-2 flex flex-col gap-0.5">
                      {group.items.map((item, i) => (
                        <li key={i} className="flex items-center justify-between text-xs">
                          <span>
                            {item.name_en}
                            {item.name_ta && <span className="ml-1.5 text-ink-faint">{item.name_ta}</span>}
                          </span>
                          <span className="font-bold">×{item.quantity}</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      onClick={() => onSelectOrder(group.orderId)}
                      className="w-full rounded-md border border-accent bg-accent-soft py-1.5 text-xs font-bold text-accent hover:bg-accent hover:text-accent-foreground"
                    >
                      Bill this ticket
                    </button>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full rounded-lg border border-border py-2 text-sm font-bold hover:bg-surface-2"
        >
          Close
        </button>
      </div>
    </div>
  );
}
