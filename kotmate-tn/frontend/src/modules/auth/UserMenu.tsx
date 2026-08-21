import { Link, useNavigate } from "react-router-dom";

import { logout } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";

interface NavLink {
  to: string;
  label: string;
}

interface UserMenuProps {
  links?: NavLink[];
}

// Shared "where am I / where can I go / how do I leave" strip for the standalone
// screens (POS, KOT Display) that don't sit inside AppShell's sidebar, plus AppShell
// itself — none of them previously wired the /auth/logout call to any button.
export function UserMenu({ links = [] }: UserMenuProps) {
  const navigate = useNavigate();
  const loginId = useAuthStore((s) => s.loginId);
  const role = useAuthStore((s) => s.role);
  const clearSession = useAuthStore((s) => s.clearSession);

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
    <div className="ml-auto flex items-center gap-2.5">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className="rounded-lg px-2.5 py-1.5 text-xs font-bold text-ink-soft hover:text-accent"
        >
          {link.label}
        </Link>
      ))}
      {/* Two stacked lines rather than one "loginId · role" line — frees up horizontal
          space in the POS header on tablet-landscape widths, where this block competes
          with the item-code field/KOT Tickets/Recall/Dashboard for room (production
          feedback). */}
      <span className="hidden flex-col leading-tight text-ink-faint sm:flex">
        <span className="text-[10.5px] font-semibold">{loginId}</span>
        <span className="text-[9.5px]">{role}</span>
      </span>
      <button
        type="button"
        onClick={() => void handleLogout()}
        className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs font-bold text-ink-soft hover:border-accent hover:text-accent"
      >
        Log out
      </button>
    </div>
  );
}
