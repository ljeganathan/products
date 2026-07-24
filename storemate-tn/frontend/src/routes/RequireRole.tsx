import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";

import { roleHomePath } from "@/routes/roleHome";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { UserRole } from "@/types/auth";

export interface RequireRoleProps {
  allow: UserRole[];
}

/** Enforces the Role -> Access Matrix (CLAUDE.md §5). Assumes it renders
 * inside <RequireAuth/>, so `user` is expected to be set; an unauthorized
 * role is redirected to that role's own home screen with a toast, never a
 * blank page. */
export function RequireRole({ allow }: RequireRoleProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const isAllowed = user ? allow.includes(user.role) : false;

  useEffect(() => {
    if (user && !isAllowed) {
      toast("danger", t("toast.unauthorizedTitle"), t("toast.unauthorizedDescription"));
    }
  }, [user, isAllowed, t]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!isAllowed) {
    return <Navigate to={roleHomePath(user.role)} replace />;
  }
  return <Outlet />;
}
