import { useEffect, useState } from "react";

import { apiClient } from "@/api/client";
import { fetchCurrentUser } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import type { AccessTokenResponse } from "@/types/auth";

/** On first load, `accessToken` is always null (it's never persisted — see
 * authStore.ts) even if the user was previously logged in. If a persisted
 * refreshToken exists, silently exchange it for a fresh access token and
 * the current user before the route guards render, so a reload doesn't
 * bounce an already-logged-in user back to /login. */
export function useAuthBootstrap(): { isBootstrapping: boolean } {
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const accessToken = useAuthStore((s) => s.accessToken);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const clear = useAuthStore((s) => s.clear);
  const [isBootstrapping, setIsBootstrapping] = useState(() => Boolean(refreshToken) && !accessToken);

  useEffect(() => {
    if (!refreshToken || accessToken) {
      setIsBootstrapping(false);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiClient.post<AccessTokenResponse>("/auth/refresh", {
          refresh_token: refreshToken,
        });
        if (cancelled) return;
        setAccessToken(data.access_token);
        const user = await fetchCurrentUser();
        if (cancelled) return;
        setUser(user);
      } catch {
        if (!cancelled) clear();
      } finally {
        if (!cancelled) setIsBootstrapping(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { isBootstrapping };
}
