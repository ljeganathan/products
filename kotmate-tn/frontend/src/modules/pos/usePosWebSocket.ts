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

  useLocationSocket(locationId, (msg) => {
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
