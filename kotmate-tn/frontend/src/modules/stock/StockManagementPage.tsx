import { StockManagementView } from "@/modules/stock/StockManagementView";

// Standalone "📦 Stock Management" screen in the main sidebar (Admin/Cashier) — moved
// out from being a tab buried inside the KOT screen (production feedback: cashiers
// need to restock between customers without a Pro-Max-only Kitchen Display screen in
// their way). KOT User keeps reaching the same shared view via its own /kot tab
// (KotDisplayPage.tsx) — that role's login is confined to /kot alone with no sidebar
// at all (CLAUDE.md §5), so this page is never itself reachable by that role.
export function StockManagementPage() {
  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-bold">📦 Stock Management</h1>
        <p className="text-xs text-foreground/60">Keep item stock counts up to date for the POS and kitchen.</p>
      </div>
      <StockManagementView />
    </div>
  );
}
