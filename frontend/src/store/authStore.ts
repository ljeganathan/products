import { create } from "zustand";
import { persist } from "zustand/middleware";

import { useToastStore } from "@/store/toastStore";
import type { AuthUser, TokenResponse } from "@/types/auth";

interface AuthState {
  /** Never persisted — kept in memory only to shrink the XSS exfiltration
   * window. Lost on a full page reload; `useAuthBootstrap` re-derives it
   * from the (persisted) refresh token instead. */
  accessToken: string | null;
  /** Persisted to localStorage. This is a pragmatic trade-off, not the
   * ideal: an httpOnly-cookie refresh flow would be safer, but the backend
   * (Phase 2) issues a plain bearer refresh token with no cookie/session
   * store, so there is nowhere else durable to keep it across reloads.
   * Revisit if Phase 9 hardening adds cookie-based refresh. */
  refreshToken: string | null;
  user: AuthUser | null;
  setSession: (tokens: TokenResponse) => void;
  setAccessToken: (accessToken: string) => void;
  setUser: (user: AuthUser) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (tokens) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user: tokens.user,
        }),
      setAccessToken: (accessToken) => set({ accessToken }),
      setUser: (user) => set({ user }),
      clear: () => {
        set({ accessToken: null, refreshToken: null, user: null });
        // A stale "access denied" toast from the previous session shouldn't
        // greet the next signed-in user (e.g. a different cashier).
        useToastStore.getState().clearAll();
      },
    }),
    {
      name: "storemate-auth",
      partialize: (state) => ({ refreshToken: state.refreshToken, user: state.user }),
    },
  ),
);
