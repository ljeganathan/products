import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useKitchenPrintStation } from "@/lib/kitchenPrintStation";
import { listLocations } from "@/modules/admin/locationsApi";
import { me } from "@/modules/auth/authApi";
import { useKitchenTicketPrinting } from "@/modules/kot/useKitchenTicketPrinting";
import { GuidedPOSPage } from "@/modules/pos/GuidedPOSPage";
import { POSPage } from "@/modules/pos/POSPage";

// Matches Tailwind's `md` breakpoint (768px) — the same cutoff Default layout's own
// CSS already uses to switch into its phone-optimized bottom-sheet UI (CartPanel's
// `hidden md:flex`, the mobile cart FAB's `md:hidden`, etc.), so "mobile" here means
// exactly what it means everywhere else in this codebase.
const MOBILE_MAX_WIDTH_QUERY = "(max-width: 767px)";

function useIsMobileViewport(): boolean {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.matchMedia(MOBILE_MAX_WIDTH_QUERY).matches,
  );
  useEffect(() => {
    const mql = window.matchMedia(MOBILE_MAX_WIDTH_QUERY);
    const onChange = () => setIsMobile(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return isMobile;
}

// Guided POS is desktop/tablet only (CLAUDE.md-adjacent Guided POS plan) — a
// phone-width viewport always gets Default layout regardless of the tenant's
// `pos_layout` setting, since the guided flow hasn't been designed for phone-sized
// screens and Default layout's mobile experience is already purpose-built for that.
export function POSLayoutRouter() {
  const { data: meData, isLoading } = useQuery({ queryKey: ["me"], queryFn: me });
  const isMobile = useIsMobileViewport();

  // Kitchen tickets from mobile orders print from whichever POS page is open, so the printing
  // lives here (above both layouts) rather than in either page. It follows the POS location.
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const [selectedLocationId, setSelectedLocationId] = useState(() => localStorage.getItem("pos-location-id"));
  useEffect(() => {
    const sync = () => setSelectedLocationId(localStorage.getItem("pos-location-id"));
    window.addEventListener("pos-location-changed", sync);
    return () => window.removeEventListener("pos-location-changed", sync);
  }, []);
  const location = locations.find((l) => l.id === selectedLocationId) ?? locations[0];
  // Off by default on the POS: only turn it on at the device that has the kitchen printer.
  const [printStation, setPrintStation] = useKitchenPrintStation(false);
  const printing = useKitchenTicketPrinting({ locationId: location?.id, enabled: printStation });

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <span className="text-sm font-semibold text-ink-faint">Loading…</span>
      </div>
    );
  }

  const page = !isMobile && meData?.pos_layout === "guided" ? <GuidedPOSPage /> : <POSPage />;
  return (
    <>
      {page}
      <div className="fixed bottom-3 left-3 z-40 flex max-w-[calc(100vw-1.5rem)] flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setPrintStation(!printStation)}
          aria-pressed={printStation}
          title="Print kitchen tickets from this device (turn on only at the device with the kitchen printer)"
          className={`rounded-full border px-2.5 py-1 text-[11px] font-bold shadow-pos ${
            printStation ? "border-veg bg-veg/15 text-veg" : "border-border bg-surface text-ink-faint"
          }`}
        >
          🖨️ Kitchen printing {printStation ? "on" : "off"}
        </button>
        {printing.notice && (
          <button
            type="button"
            onClick={printing.dismiss}
            role="alert"
            className="rounded-lg bg-chili-soft px-3 py-1.5 text-left text-[11px] font-semibold text-chili shadow-pos"
          >
            Kitchen ticket didn&apos;t print: {printing.notice}. Tap to dismiss.
          </button>
        )}
      </div>
    </>
  );
}
