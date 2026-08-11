import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import logoMark from "@/assets/logo-mark.png";
import { playNewTicketSound } from "@/lib/notifySound";
import { listItems } from "@/modules/admin/itemsApi";
import { listLocations } from "@/modules/admin/locationsApi";
import { me } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";
import { UserMenu } from "@/modules/auth/UserMenu";
import { type ActiveKotTicket, listActiveKotTickets, updateKotTicketStatus } from "@/modules/pos/kotApi";
import { useLocationSocket } from "@/modules/realtime/useLocationSocket";

import { KotTicketCard } from "./KotTicketCard";
import { StockManagementTab } from "./StockManagementTab";

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
  const [view, setView] = useState<"tickets" | "stock">("tickets");

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  // Pro/Pro Max-only surface (the tab strip itself) — the badges below stay on for
  // Lite too, gated separately on the Lite-inclusive effective flag.
  const stockManagementOnPlan = meData?.features?.stock_management === true;
  const stockTrackingEnabled = meData?.stock_tracking_enabled === true;

  const { data: locations = [], isLoading: locationsLoading } = useQuery({
    queryKey: ["tenant-locations"],
    queryFn: listLocations,
  });
  // Persisted per-device, same pattern as POSPage's location picker (POS-35) — a
  // Kitchen Display is normally a fixed screen mounted at one physical kitchen, so it
  // shouldn't need re-picking after every reload. This also fixes a real bug: the
  // realtime `kot_ticket`/`item_stock` websocket is scoped strictly per location
  // server-side (ws/manager.py), so silently defaulting to `locations[0]` meant a
  // multi-location tenant's Kitchen Display could be subscribed to the wrong branch
  // and never see new tickets arrive live, only via the 15s poll fallback.
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(() =>
    localStorage.getItem("kot-location-id"),
  );
  const location = locations.find((l) => l.id === selectedLocationId) ?? locations[0];
  useEffect(() => {
    if (location && location.id !== selectedLocationId) {
      setSelectedLocationId(location.id);
      localStorage.setItem("kot-location-id", location.id);
    }
  }, [location, selectedLocationId]);

  function handleLocationChange(nextId: string) {
    localStorage.setItem("kot-location-id", nextId);
    setSelectedLocationId(nextId);
  }

  const { data: tickets = [], isLoading } = useQuery({
    queryKey: ["kot-tickets-active", location?.id],
    queryFn: () => listActiveKotTickets(location?.id),
    // Wait for the locations list to resolve so this doesn't fire once unscoped (all
    // locations) and then again once `location` settles — see the comment above on
    // why an unscoped fetch also means an unscoped (wrong-branch) websocket otherwise.
    enabled: !locationsLoading,
    refetchInterval: 15_000,
  });

  const { data: items = [] } = useQuery({
    queryKey: ["kds-tracked-items"],
    queryFn: () => listItems(),
  });

  useLocationSocket(location?.id, (msg) => {
    if (msg.type === "kot_ticket") {
      // Only a brand-new ticket starts life with status "new" — a status-update
      // broadcast (kitchen staff marking one preparing/ready) reuses the same message
      // shape but never carries that value, so this is how a "new order" chime stays
      // a chime for new orders instead of firing on every tap in this same screen.
      if (msg.status === "new") playNewTicketSound();
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
    .filter((item) => item.track_inventory && stockTrackingEnabled)
    .map((item) => {
      const override = stockOverrides[item.id];
      const availableQty = override ? override.available_qty : item.available_qty;
      return { ...item, availableQty };
    })
    .filter((item) => item.availableQty !== null && item.availableQty <= 5);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex items-center gap-2.5 border-b border-border bg-surface px-4 py-2.5 shadow-pos">
        <img src={logoMark} alt="KOTMate TN" className="h-7 w-7 object-contain" />
        <span className="text-[13px] font-extrabold leading-none">Kitchen Display</span>

        {location && locations.length > 1 && (
          <select
            value={location.id}
            onChange={(e) => handleLocationChange(e.target.value)}
            className="min-h-8 max-w-[140px] truncate rounded-lg border border-border bg-surface-2 px-2 text-xs font-semibold text-ink-soft outline-none"
          >
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name}
              </option>
            ))}
          </select>
        )}

        {stockManagementOnPlan && (
          <div className="ml-2 flex gap-1">
            {(["tickets", "stock"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors ${
                  view === v
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border bg-surface-2 text-ink-soft hover:border-accent"
                }`}
              >
                {v === "tickets" ? "🍳 Kitchen Orders" : "📦 Stock Management"}
              </button>
            ))}
          </div>
        )}

        {role === "tenant_admin" && (
          <Link
            to="/dashboard"
            className="ml-auto flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
          >
            📊 Dashboard
          </Link>
        )}

        <UserMenu />
      </header>

      {view === "tickets" && lowStockItems.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-chili-soft px-4 py-2">
          <span className="text-xs font-extrabold text-chili">⚠ Low stock:</span>
          {lowStockItems.map((item) => (
            <span key={item.id} className="rounded-full bg-surface px-2.5 py-1 text-xs font-bold text-chili">
              {item.name_en} — {item.availableQty === 0 ? "out" : `${item.availableQty} left`}
            </span>
          ))}
        </div>
      )}

      {view === "stock" && stockManagementOnPlan ? (
        <StockManagementTab />
      ) : (
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
      )}
    </div>
  );
}
