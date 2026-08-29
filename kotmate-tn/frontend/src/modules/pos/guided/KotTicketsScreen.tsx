import { KotTicketsList } from "@/modules/pos/KotTicketsList";

interface KotTicketsScreenProps {
  onSelectOrder: (orderId: string) => void;
}

// Full-screen version of the real KotTicketsPopup — same grouped-by-order list, same
// "Bill this ticket" action, no status-advance controls (that's the separate Kitchen
// Display screen's job). Selecting a ticket jumps the left rail back to Billing with
// that order loaded.
export function KotTicketsScreen({ onSelectOrder }: KotTicketsScreenProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
        <h2 className="mb-1 text-lg font-extrabold">🍳 KOT Tickets</h2>
        <p className="mb-4 text-xs text-ink-faint">
          Open kitchen tickets from any device — select one to bill it here.
        </p>
        <KotTicketsList onSelectOrder={onSelectOrder} />
      </div>
    </div>
  );
}
