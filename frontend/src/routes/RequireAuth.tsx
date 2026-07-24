import { Navigate, Outlet, useLocation } from "react-router-dom";

import { FullScreenSpinner } from "@/components/ui/Spinner";
import { useAuthBootstrap } from "@/hooks/useAuthBootstrap";
import { useAuthStore } from "@/store/authStore";

/** Gate for every non-public route. On a fresh page load the in-memory
 * accessToken is always empty (see authStore.ts), so this waits for
 * useAuthBootstrap to attempt a silent refresh before deciding whether the
 * visitor is actually signed out. */
export function RequireAuth() {
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const { isBootstrapping } = useAuthBootstrap();

  if (isBootstrapping) {
    return <FullScreenSpinner />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
