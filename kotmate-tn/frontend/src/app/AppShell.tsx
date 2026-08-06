import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/modules/auth/authStore";

// "pos", "kot", "reports", and "settings" render as real links below (role-gated)
// since Phase 07/08/10/11 built them; the rest stay static placeholders until their
// own phase lands. "dashboard" isn't in this list — AppShell itself only ever wraps
// the Dashboard page (see router.tsx), so a self-link back to the current page would
// be pointless.
const NAV_ITEMS = ["items", "waiters"] as const;

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { t, i18n } = useTranslation();
  const role = useAuthStore((state) => state.role);

  const toggleLanguage = () => {
    void i18n.changeLanguage(i18n.language === "en" ? "ta" : "en");
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Desktop / tablet sidebar */}
      <aside className="hidden w-56 flex-none flex-col border-r border-border p-4 md:flex">
        <span className="mb-6 text-lg font-bold">{t("app.name")}</span>
        <nav className="flex flex-col gap-1">
          {role !== "kitchen" && (
            <Link
              to="/pos"
              className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
            >
              {t("nav.pos")}
            </Link>
          )}
          {role === "tenant_admin" && (
            <Link
              to="/kot"
              className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
            >
              {t("nav.kot")}
            </Link>
          )}
          {(role === "tenant_admin" || role === "pos_user") && (
            <>
              <Link
                to="/reports"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                {t("nav.reports")}
              </Link>
              <Link
                to="/billing/history"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Bill History
              </Link>
            </>
          )}
          {NAV_ITEMS.map((key) => (
            <span
              key={key}
              className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
            >
              {t(`nav.${key}`)}
            </span>
          ))}
          {role === "tenant_admin" && (
            <>
              <Link
                to="/admin/categories"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Categories
              </Link>
              <Link
                to="/admin/items"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Item Master
              </Link>
              <Link
                to="/admin/waiters"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Waiter Master
              </Link>
              <Link
                to="/admin/sections"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Seating Sections
              </Link>
              <Link
                to="/admin/tables"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Table Master
              </Link>
              <Link
                to="/admin/printers"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Printers
              </Link>
              <Link
                to="/admin/tax-rules"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Tax Rules
              </Link>
              <Link
                to="/admin/discount-rules"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Discount Rules
              </Link>
              <Link
                to="/admin/users"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                Users
              </Link>
              <Link
                to="/admin/settings"
                className="rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
              >
                {t("nav.settings")}
              </Link>
            </>
          )}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h1 className="text-base font-semibold">{t("app.name")}</h1>
            <p className="text-xs text-foreground/60">{t("app.tagline")}</p>
          </div>
          <button
            type="button"
            onClick={toggleLanguage}
            data-testid="lang-toggle"
            className={cn(
              "rounded-full border border-border px-3 py-1 text-xs font-semibold",
              "hover:bg-accent/10",
            )}
          >
            {i18n.language === "en" ? "EN / தமிழ்" : "தமிழ் / EN"}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 flex justify-around border-t border-border bg-background py-2 md:hidden">
        {NAV_ITEMS.map((key) => (
          <span key={key} className="px-2 text-[11px] text-foreground/70">
            {t(`nav.${key}`)}
          </span>
        ))}
      </nav>
    </div>
  );
}
