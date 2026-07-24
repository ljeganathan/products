import { LogOut, Store } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout as apiLogout } from "@/api/auth";
import { LanguageToggle } from "@/components/LanguageToggle";
import { MaintenanceBanner } from "@/components/MaintenanceBanner";
import { NotificationBell } from "@/components/NotificationBell";
import { navItemsForRole, type NavItem } from "@/layouts/navConfig";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/utils/cn";

function NavLinkItem({ item, compact = false }: { item: NavItem; compact?: boolean }) {
  const { t } = useTranslation();
  const Icon = item.icon;

  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-lg text-sm font-medium transition-colors",
          compact
            ? "min-w-[4.5rem] flex-col justify-center gap-1 px-2 py-1.5 text-xs"
            : "px-3 py-2.5",
          isActive
            ? "bg-brand-50 text-brand-700"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
        )
      }
    >
      <Icon className={compact ? "h-5 w-5" : "h-5 w-5 shrink-0"} aria-hidden="true" />
      <span className={compact ? "leading-none" : ""}>{t(item.labelKey)}</span>
    </NavLink>
  );
}

export function AppLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);

  if (!user) return null;
  const navItems = navItemsForRole(user.role);

  async function handleLogout() {
    try {
      await apiLogout();
    } catch {
      // Stateless JWT logout — nothing to reconcile server-side either way.
    }
    clear();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop / landscape-tablet sidebar (>= 1024px) */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 items-center gap-2 border-b border-slate-200 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Store className="h-5 w-5" aria-hidden="true" />
          </div>
          <span className="font-display text-lg font-semibold text-slate-900">
            {t("app.name")}
          </span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
          {navItems.map((item) => (
            <NavLinkItem key={item.to} item={item} />
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            <LogOut className="h-5 w-5" aria-hidden="true" />
            {t("common.logout")}
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-60">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex items-center gap-2 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Store className="h-4 w-4" aria-hidden="true" />
            </div>
            <span className="font-display text-base font-semibold text-slate-900">
              {t("app.name")}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {user.role === "admin" && <NotificationBell />}
            <LanguageToggle />
            <div className="hidden items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 sm:flex">
              <span className="text-sm font-medium text-slate-700">{user.name}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                {t(`roles.${user.role}`)}
              </span>
            </div>
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 lg:hidden"
              aria-label={t("common.logout")}
            >
              <LogOut className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </header>

        <MaintenanceBanner />

        <main className="flex-1 px-4 pb-24 pt-6 sm:px-6 lg:pb-6">
          <Outlet />
        </main>
      </div>

      {/* Compact bottom nav bar for tablets narrower than 1024px */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around gap-1 overflow-x-auto border-t border-slate-200 bg-white px-2 py-1 lg:hidden">
        {navItems.map((item) => (
          <NavLinkItem key={item.to} item={item} compact />
        ))}
      </nav>
    </div>
  );
}
