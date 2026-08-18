import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useLocationSocket } from "@/modules/realtime/useLocationSocket";

export interface StockOverride {
  available_qty: number;
  low_stock: boolean;
  out_of_stock: boolean;
}

type StockOverrides = Record<string, StockOverride>;

// Live low-stock/86'd overrides for the POS item grid (CLAUDE.md §11), sourced from the
// same /ws/location/{id} channel (Phase 08) the Kitchen Display uses for its own banner.
export function usePosWebSocket(locationId: string | undefined): StockOverrides {
  const [overrides, setOverrides] = useState<StockOverrides>({});
  const queryClient = useQueryClient();

  useLocationSocket(locationId, (msg) => {
    if (msg.type === "top_sellers_changed") {
      // Bill just finalized somewhere at this location — nudge the Top Selling tab
      // (1-hour rolling window, item_service.list_top_sellers) to refetch. No payload,
      // this is purely a signal. A 60s refetchInterval on that query (POSPage.tsx) is
      // the fallback for the case this message doesn't land (see manager.py: in-memory,
      // per-worker-process fan-out — a bill finalized on one gunicorn worker won't reach
      // a websocket connection pinned to another).
      void queryClient.invalidateQueries({ queryKey: ["pos-top-sellers"] });
      return;
    }
    if (msg.type !== "item_stock") return;
    setOverrides((prev) => ({
      ...prev,
      [msg.item_id as string]: {
        available_qty: msg.available_qty as number,
        low_stock: msg.low_stock as boolean,
        out_of_stock: msg.out_of_stock as boolean,
      },
    }));
  });

  return overrides;
}
