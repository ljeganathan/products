import { create } from "zustand";
import { persist } from "zustand/middleware";

// CLAUDE.md §5 — the five RBAC roles, product_owner included (never a separate app).
export type Role = "product_owner" | "tenant_admin" | "pos_user" | "waiter" | "kitchen";

export interface Session {
  accessToken: string;
  refreshToken: string;
  role: Role;
  tenantId: string | null;
  loginId: string;
}

interface AuthState extends Partial<Session> {
  setSession: (session: Session) => void;
  clearSession: () => void;
}

// Persisted (not just in-memory) so a page refresh doesn't force a re-login — the
// axios interceptor and route guards both read this via getState() outside React.
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: undefined,
      refreshToken: undefined,
      role: undefined,
      tenantId: undefined,
      loginId: undefined,
      setSession: (session) => set(session),
      clearSession: () =>
        set({
          accessToken: undefined,
          refreshToken: undefined,
          role: undefined,
          tenantId: undefined,
          loginId: undefined,
        }),
    }),
    { name: "kotmate-auth" },
  ),
);

export function roleHomePath(role: Role): string {
  switch (role) {
    case "product_owner":
      return "/platform";
    case "tenant_admin":
      return "/dashboard";
    case "pos_user":
    case "waiter":
      return "/pos";
    case "kitchen":
      return "/kot";
  }
}
