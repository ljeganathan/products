import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { cn } from "@/lib/utils";
import { logout } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";

const NAV_ITEMS = [
  { to: "/platform", label: "Dashboard", end: true },
  { to: "/platform/tenants", label: "Tenants" },
  { to: "/platform/invoices", label: "Invoices" },
  { to: "/platform/plans", label: "Plans" },
  { to: "/platform/maintenance", label: "Maintenance" },
] as const;

export function PlatformShell() {
  const navigate = useNavigate();
  const loginId = useAuthStore((state) => state.loginId);
  const clearSession = useAuthStore((state) => state.clearSession);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // stateless JWT (no server-side session) — clear locally regardless of outcome
    }
    clearSession();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen w-screen bg-background text-foreground">
      <aside className="flex h-screen w-56 flex-none flex-col border-r border-border p-4">
        <Link to="/platform" className="mb-1 text-lg font-bold">
          KOTMate TN
        </Link>
        <span className="mb-6 text-xs font-semibold uppercase tracking-wide text-chili">
          Platform Console
        </span>
        <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={"end" in item ? item.end : false}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium",
                  isActive ? "bg-accent text-accent-foreground" : "text-foreground/70 hover:bg-accent/10",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex flex-none flex-col gap-2 border-t border-border pt-4">
          <span className="text-xs text-foreground/60">{loginId}</span>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="self-start rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10"
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
