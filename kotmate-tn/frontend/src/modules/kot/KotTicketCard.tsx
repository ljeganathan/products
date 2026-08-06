import type { ActiveKotTicket } from "@/modules/pos/kotApi";

interface KotTicketCardProps {
  ticket: ActiveKotTicket;
  canAdvance: boolean;
  advancing: boolean;
  onAdvance: (ticketId: string, nextStatus: "preparing" | "ready") => void;
}

const STATUS_ACCENT: Record<string, string> = {
  new: "border-border",
  preparing: "border-gold",
  ready: "border-veg",
};

// Table number is the dominant visual anchor everywhere (CLAUDE.md §9) — bigger/bolder
// than anything else on the card, section/class shown as a smaller badge beside it.
// Non-seating sections (Takeaway/Online Delivery) have no table_number at all, so the
// section name itself takes the big-anchor spot instead.
export function KotTicketCard({ ticket, canAdvance, advancing, onAdvance }: KotTicketCardProps) {
  const createdTime = new Date(ticket.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <li
      className={`rounded-xl border-2 bg-surface p-3.5 shadow-pos ${STATUS_ACCENT[ticket.status] ?? "border-border"}`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-baseline gap-1.5">
          {ticket.table_number ? (
            <>
              <span className="text-2xl font-black leading-none">{ticket.table_number}</span>
              <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-extrabold text-accent">
                {ticket.section_name_en}
              </span>
            </>
          ) : (
            <span className="text-lg font-black leading-none">{ticket.section_name_en}</span>
          )}
        </div>
        <span className="text-[11px] font-semibold text-ink-faint">{createdTime}</span>
      </div>

      <p className="mb-2 font-mono text-[11px] text-ink-faint">#{ticket.ticket_number}</p>

      <ul className="mb-3 flex flex-col gap-1">
        {ticket.items.map((item, idx) => (
          <li key={idx} className="flex items-baseline justify-between gap-2 text-sm">
            <span>
              <span className="font-semibold">{item.name_en}</span>
              {item.name_ta && <span className="ml-1.5 text-xs text-ink-faint">{item.name_ta}</span>}
            </span>
            <span className="font-bold">×{item.quantity}</span>
          </li>
        ))}
      </ul>

      {canAdvance && ticket.status === "new" && (
        <button
          type="button"
          disabled={advancing}
          onClick={() => onAdvance(ticket.id, "preparing")}
          className="w-full rounded-lg bg-gold py-2 text-xs font-extrabold text-accent-foreground disabled:opacity-50"
        >
          Start Preparing
        </button>
      )}
      {canAdvance && ticket.status === "preparing" && (
        <button
          type="button"
          disabled={advancing}
          onClick={() => onAdvance(ticket.id, "ready")}
          className="w-full rounded-lg bg-veg py-2 text-xs font-extrabold text-accent-foreground disabled:opacity-50"
        >
          Mark Ready
        </button>
      )}
      {ticket.status === "ready" && (
        <p className="text-center text-xs font-bold text-veg">Ready for pickup</p>
      )}
    </li>
  );
}
