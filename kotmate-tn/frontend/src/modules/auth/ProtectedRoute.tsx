import { Navigate, Outlet } from "react-router-dom";

import { roleHomePath, useAuthStore, type Role } from "@/modules/auth/authStore";

interface ProtectedRouteProps {
  roles: Role[];
}

// Wraps a set of routes (as children, via <Outlet/>) behind login + an RBAC role
// check. A logged-in user hitting a route their role doesn't cover is bounced to
// their own home, not just shown a dead end — e.g. a tenant_admin hitting /platform
// lands back on /dashboard rather than a blank/error page.
export function ProtectedRoute({ roles }: ProtectedRouteProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const role = useAuthStore((state) => state.role);

  if (!accessToken || !role) {
    return <Navigate to="/login" replace />;
  }

  if (!roles.includes(role)) {
    return <Navigate to={roleHomePath(role)} replace />;
  }

  return <Outlet />;
}
