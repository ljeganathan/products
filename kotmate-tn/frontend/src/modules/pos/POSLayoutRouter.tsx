import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { me } from "@/modules/auth/authApi";
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

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <span className="text-sm font-semibold text-ink-faint">Loading…</span>
      </div>
    );
  }

  if (!isMobile && meData?.pos_layout === "guided") {
    return <GuidedPOSPage />;
  }
  return <POSPage />;
}
