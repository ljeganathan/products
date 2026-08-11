import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import logoFull from "@/assets/logo-full.png";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/modules/auth/authStore";
import { UserMenu } from "@/modules/auth/UserMenu";

interface AppShellProps {
  children: ReactNode;
}

function NavItem({
  to,
  icon,
  label,
  onNavigate,
}: {
  to: string;
  icon: string;
  label: string;
  onNavigate: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-foreground/70 hover:bg-accent/10"
    >
      <span className="w-4 text-center" aria-hidden="true">
        {icon}
      </span>
      {label}
    </Link>
  );
}

export function AppShell({ children }: AppShellProps) {
  const { t, i18n } = useTranslation();
  const role = useAuthStore((state) => state.role);
  // Below `md` the sidebar itself is hidden (see the `<aside>` below) — without this
  // drawer there was no way to reach any nav link at all on a phone/portrait tablet
  // once past the first page (found during real-device testing).
  const [navOpen, setNavOpen] = useState(false);

  const toggleLanguage = () => {
    void i18n.changeLanguage(i18n.language === "en" ? "ta" : "en");
  };

  function renderNavLinks(onNavigate: () => void) {
    return (
      <nav className="flex flex-col gap-1">
        {(role === "tenant_admin" || role === "pos_user") && (
          <NavItem to="/dashboard" icon="📊" label="Dashboard" onNavigate={onNavigate} />
        )}
        {role !== "kitchen" && <NavItem to="/pos" icon="🧾" label={t("nav.pos")} onNavigate={onNavigate} />}
        {role === "tenant_admin" && <NavItem to="/kot" icon="🍳" label={t("nav.kot")} onNavigate={onNavigate} />}
        {(role === "tenant_admin" || role === "pos_user") && (
          <>
            <NavItem to="/reports" icon="📈" label={t("nav.reports")} onNavigate={onNavigate} />
            <NavItem to="/billing/history" icon="🧮" label="Bill History" onNavigate={onNavigate} />
          </>
        )}
        {role === "tenant_admin" && (
          <>
            <NavItem to="/admin/categories" icon="🗂️" label="Categories" onNavigate={onNavigate} />
            <NavItem to="/admin/items" icon="🍽️" label="Item Master" onNavigate={onNavigate} />
            <NavItem to="/admin/waiters" icon="🧑‍🍳" label="Waiter Master" onNavigate={onNavigate} />
            <NavItem to="/admin/sections" icon="🪑" label="Seating Sections" onNavigate={onNavigate} />
            <NavItem to="/admin/tables" icon="🔢" label="Table Master" onNavigate={onNavigate} />
            <NavItem to="/admin/printers" icon="🖨️" label="Printers" onNavigate={onNavigate} />
            <NavItem to="/admin/tax-rules" icon="💰" label="Tax Rules" onNavigate={onNavigate} />
            <NavItem to="/admin/discount-rules" icon="🏷️" label="Discount Rules" onNavigate={onNavigate} />
            <NavItem to="/admin/users" icon="👥" label="Users" onNavigate={onNavigate} />
            <NavItem to="/admin/settings" icon="⚙️" label={t("nav.settings")} onNavigate={onNavigate} />
          </>
        )}
      </nav>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Desktop / tablet sidebar */}
      <aside className="hidden w-56 flex-none flex-col border-r border-border p-4 md:flex">
        <img src={logoFull} alt={t("app.name")} className="mb-6 h-auto w-full max-w-[176px]" />
        {renderNavLinks(() => {})}
      </aside>

      {/* Mobile nav drawer — same slide-in-panel + backdrop convention as the POS
          mobile cart sheet (POSPage.tsx), so this reads as one consistent pattern. */}
      {navOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="absolute inset-0 bg-black/45" onClick={() => setNavOpen(false)} />
          <div className="relative flex h-full w-72 max-w-[80vw] flex-col overflow-y-auto bg-background p-4 shadow-pos">
            <div className="mb-6 flex items-center justify-between">
              <img src={logoFull} alt={t("app.name")} className="h-auto w-full max-w-[160px]" />
              <button
                type="button"
                onClick={() => setNavOpen(false)}
                aria-label="Close menu"
                className="flex min-h-9 min-w-9 items-center justify-center rounded-md text-xl leading-none hover:bg-accent/10"
              >
                ✕
              </button>
            </div>
            {renderNavLinks(() => setNavOpen(false))}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              aria-label="Open menu"
              className="flex min-h-9 min-w-9 items-center justify-center rounded-md text-xl leading-none hover:bg-accent/10 md:hidden"
            >
              ☰
            </button>
            <div>
              <h1 className="text-base font-semibold">{t("app.name")}</h1>
              <p className="text-xs text-foreground/60">{t("app.tagline")}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
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
            <UserMenu />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
