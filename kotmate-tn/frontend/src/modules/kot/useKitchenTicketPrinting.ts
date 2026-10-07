import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { printKotTicketFromServer } from "@/lib/printDispatch";
import { claimKotTicketPrint, listActiveKotTickets } from "@/modules/pos/kotApi";
import { useLocationSocket } from "@/modules/realtime/useLocationSocket";

// Prints kitchen tickets from this browser, for a Bluetooth/USB/RawBT kitchen printer that only
// this device can reach. Used by the Kitchen Display and by every POS page, so a mobile order
// prints even when the POS is the screen that's open.
//
// Two paths, both through the same claim (the server gives the job to one screen only):
//   1. the live `kot_ticket` message, as soon as a ticket fires;
//   2. the 15-second ticket refresh, for a ticket this screen saw appear but never heard about
//      (its socket was down). Tickets already on screen when the page opened are never printed.
export function useKitchenTicketPrinting({
  locationId,
  enabled,
}: {
  locationId: string | undefined;
  enabled: boolean;
}): { notice: string | null; dismiss: () => void } {
  const [notice, setNotice] = useState<string | null>(null);
  const seen = useRef<{ locationId: string; ticketIds: Set<string> } | null>(null);

  const { data: tickets = [], isSuccess } = useQuery({
    queryKey: ["kot-tickets-active", locationId],
    queryFn: () => listActiveKotTickets(locationId),
    enabled: !!locationId,
    refetchInterval: 15_000,
  });

  function print(ticketId: string) {
    void printKotTicketFromServer(ticketId, () => claimKotTicketPrint(ticketId)).then((error) => {
      if (error) setNotice(error);
    });
  }

  useEffect(() => {
    if (!isSuccess || !locationId) return;
    const current = seen.current;
    if (!current || current.locationId !== locationId) {
      // First load for this location: whatever is already on screen is baseline, not new.
      seen.current = { locationId, ticketIds: new Set(tickets.map((t) => t.id)) };
      return;
    }
    for (const ticket of tickets) {
      if (current.ticketIds.has(ticket.id)) continue;
      current.ticketIds.add(ticket.id);
      if (enabled && !ticket.is_pending_takeaway) print(ticket.id);
    }
  }, [tickets, isSuccess, locationId, enabled]);

  useLocationSocket(locationId, (msg) => {
    if (msg.type !== "kot_ticket" || !enabled || !msg.print_job || typeof msg.id !== "string") return;
    print(msg.id);
  });

  return { notice, dismiss: () => setNotice(null) };
}
