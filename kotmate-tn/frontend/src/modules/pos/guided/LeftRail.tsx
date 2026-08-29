export type GuidedArea = "billing" | "kot-tickets" | "fast-billing" | "recall";

interface LeftRailProps {
  activeArea: GuidedArea;
  onSelectArea: (area: GuidedArea) => void;
  kotTicketsVisible: boolean;
  openTicketCount: number;
}

// Entry-chooser nav — Billing / KOT Tickets / Recall / Fast Billing. "KOT Tickets"
// only appears when the tenant's plan has the KDS feature (Pro Max), same gate
// Default layout's header button uses. Only ever rendered while the cashier is
// choosing what to do next (Order Type, KOT Tickets, Recall, Fast Billing) —
// GuidedPOSPage hides this entirely once a specific order's Item+Cart screen is
// open, so billing gets the full screen width with no competing nav.
export function LeftRail({ activeArea, onSelectArea, kotTicketsVisible, openTicketCount }: LeftRailProps) {
  return (
    <div className="flex w-[84px] flex-none flex-col items-stretch gap-2 border-r border-border bg-surface-2 p-2">
      <RailButton
        icon="🧾"
        label="Billing"
        active={activeArea === "billing"}
        onClick={() => onSelectArea("billing")}
      />
      {kotTicketsVisible && (
        <RailButton
          icon="🎫"
          label="KOT Tickets"
          active={activeArea === "kot-tickets"}
          onClick={() => onSelectArea("kot-tickets")}
          badge={openTicketCount > 0 ? openTicketCount : undefined}
        />
      )}
      <RailButton
        icon="↺"
        label="Recall"
        active={activeArea === "recall"}
        onClick={() => onSelectArea("recall")}
      />
      <RailButton
        icon="⚡"
        label="Fast Billing"
        active={activeArea === "fast-billing"}
        onClick={() => onSelectArea("fast-billing")}
      />
    </div>
  );
}

function RailButton({
  icon,
  label,
  active,
  onClick,
  badge,
}: {
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
  badge?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-col items-center gap-1 rounded-xl border px-1 py-3 text-center text-[10.5px] font-extrabold leading-tight transition-colors ${
        active
          ? "border-accent bg-surface text-accent shadow-pos"
          : "border-transparent text-ink-soft hover:bg-surface-3"
      }`}
    >
      <span className="text-xl">{icon}</span>
      {label}
      {badge !== undefined && (
        <span className="absolute right-1.5 top-1.5 min-w-[15px] rounded-full bg-chili px-1 text-[9.5px] font-extrabold text-white">
          {badge}
        </span>
      )}
    </button>
  );
}
