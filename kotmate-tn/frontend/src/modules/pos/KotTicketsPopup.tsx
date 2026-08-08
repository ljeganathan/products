import { useQuery } from "@tanstack/react-query";

import { listActiveKotTickets } from "@/modules/pos/kotApi";

interface KotTicketsPopupProps {
  onSelectOrder: (orderId: string) => void;
  onClose: () => void;
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
        {data && data.length === 0 && (
          <p className="text-sm text-ink-faint">No open kitchen tickets right now.</p>
        )}
        {data && data.length > 0 && (
          <ul className="flex flex-col gap-2">
            {data.map((ticket) => (
              <li key={ticket.id} className="overflow-hidden rounded-lg border border-border bg-surface-2">
                <details>
                  <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 marker:content-none">
                    <span>
                      <span className="font-mono text-xs text-ink-faint">#{ticket.ticket_number}</span>
                      <span className="ml-2 text-lg font-black">{ticket.table_number ?? "—"}</span>
                      <span className="ml-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-extrabold text-accent">
                        {ticket.section_name_en}
                      </span>
                    </span>
                    <span className="text-xs font-semibold capitalize text-ink-faint">{ticket.status}</span>
                  </summary>
                  <div className="border-t border-dashed border-border px-3.5 py-2">
                    <ul className="mb-2 flex flex-col gap-0.5">
                      {ticket.items.map((item, i) => (
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
                      onClick={() => onSelectOrder(ticket.order_id)}
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
