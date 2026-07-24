import { LogOut, Store } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { logout as apiLogout } from "@/api/auth";
import { LanguageToggle } from "@/components/LanguageToggle";
import { MaintenanceBanner } from "@/components/MaintenanceBanner";
import { useAuthStore } from "@/store/authStore";

/** POS is a dedicated, full-viewport experience — no persistent sidebar, no
 * page chrome competing with the cart/keypad. Just a slim exit strip so a
 * cashier can still get back to their other screens or sign out. */
export function PosLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);

  if (!user) return null;

  async function handleLogout() {
    try {
      await apiLogout();
    } catch {
      // Stateless JWT logout — nothing to reconcile server-side either way.
    }
    clear();
    navigate("/login", { replace: true });
  }

  const homePath = user.role === "admin" ? "/dashboard" : "/pos";

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-100">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4">
        <Link to={homePath} className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Store className="h-4 w-4" aria-hidden="true" />
          </div>
          <span className="font-display text-base font-semibold text-slate-900">
            {t("app.name")}
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <LanguageToggle />
          <span className="hidden text-sm font-medium text-slate-600 sm:inline">{user.name}</span>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label={t("common.logout")}
          >
            <LogOut className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>

      <MaintenanceBanner />

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
