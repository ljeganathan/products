import { KotTicketsList } from "@/modules/pos/KotTicketsList";

interface KotTicketsPopupProps {
  onSelectOrder: (orderId: string) => void;
  onClose: () => void;
}

// Modal chrome around the shared KotTicketsList — Guided POS's KotTicketsScreen mounts
// that same list full-height instead, with no popup wrapper.
export function KotTicketsPopup({ onSelectOrder, onClose }: KotTicketsPopupProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-2xl bg-surface p-5 shadow-pos">
        <h2 className="mb-1 text-lg font-extrabold">🍳 KOT Tickets</h2>
        <p className="mb-4 text-xs text-ink-faint">
          Open kitchen tickets from any device — select one to bill it here.
        </p>

        <KotTicketsList onSelectOrder={onSelectOrder} />

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
