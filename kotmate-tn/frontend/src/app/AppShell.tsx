import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/modules/auth/authStore";
import { UserMenu } from "@/modules/auth/UserMenu";

interface AppShellProps {
  children: ReactNode;
}

function NavItem({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <Link
      to={to}
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

  const toggleLanguage = () => {
    void i18n.changeLanguage(i18n.language === "en" ? "ta" : "en");
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Desktop / tablet sidebar */}
      <aside className="hidden w-56 flex-none flex-col border-r border-border p-4 md:flex">
        <span className="mb-6 text-lg font-bold">{t("app.name")}</span>
        <nav className="flex flex-col gap-1">
          {(role === "tenant_admin" || role === "pos_user") && (
            <NavItem to="/dashboard" icon="📊" label="Dashboard" />
          )}
          {role !== "kitchen" && <NavItem to="/pos" icon="🧾" label={t("nav.pos")} />}
          {role === "tenant_admin" && <NavItem to="/kot" icon="🍳" label={t("nav.kot")} />}
          {(role === "tenant_admin" || role === "pos_user") && (
            <>
              <NavItem to="/reports" icon="📈" label={t("nav.reports")} />
              <NavItem to="/billing/history" icon="🧮" label="Bill History" />
            </>
          )}
          {role === "tenant_admin" && (
            <>
              <NavItem to="/admin/categories" icon="🗂️" label="Categories" />
              <NavItem to="/admin/items" icon="🍽️" label="Item Master" />
              <NavItem to="/admin/waiters" icon="🧑‍🍳" label="Waiter Master" />
              <NavItem to="/admin/sections" icon="🪑" label="Seating Sections" />
              <NavItem to="/admin/tables" icon="🔢" label="Table Master" />
              <NavItem to="/admin/printers" icon="🖨️" label="Printers" />
              <NavItem to="/admin/tax-rules" icon="💰" label="Tax Rules" />
              <NavItem to="/admin/discount-rules" icon="🏷️" label="Discount Rules" />
              <NavItem to="/admin/users" icon="👥" label="Users" />
              <NavItem to="/admin/settings" icon="⚙️" label={t("nav.settings")} />
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
