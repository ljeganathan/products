import { useEffect, useRef } from "react";

import { useAuthStore } from "@/modules/auth/authStore";

const MAX_BACKOFF_MS = 30_000;

export type LocationSocketMessage = Record<string, unknown> & { type: string };

// Shared /ws/location/{id} channel (Phase 08) — the POS grid (item_stock low-stock
// overrides) and the Kitchen Display (kot_ticket + item_stock) each open their own
// connection via this hook, since the backend's connection manager broadcasts
// per-location to every open socket regardless of which screen opened it. The browser's
// native WebSocket can't set an Authorization header, so the token travels as a query
// param instead — read fresh on every (re)connect attempt, not just on mount, so a
// token refreshed mid-session is picked up by the next reconnect rather than being
// stuck with a stale one.
export function useLocationSocket(
  locationId: string | undefined,
  onMessage: (message: LocationSocketMessage) => void,
): void {
  const attemptRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!locationId) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

    function connect() {
      if (cancelled) return;
      const token = useAuthStore.getState().accessToken;
      if (!token) {
        scheduleReconnect();
        return;
      }

      const wsUrl = `${apiBase.replace(/^http/, "ws")}/ws/location/${locationId}?token=${encodeURIComponent(token)}`;
      try {
        socket = new WebSocket(wsUrl);
      } catch {
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        attemptRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as LocationSocketMessage;
          onMessageRef.current(msg);
        } catch {
          // Malformed frame — ignore rather than crash the caller over it.
        }
      };

      socket.onclose = scheduleReconnect;
      socket.onerror = () => socket?.close();
    }

    function scheduleReconnect() {
      if (cancelled) return;
      const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF_MS);
      attemptRef.current += 1;
      reconnectTimer = setTimeout(connect, delay);
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [locationId]);
}
