import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { listStock } from "@/api/stock";
import type { Stock } from "@/types/stock";

// Mirrors useItemCatalog's caching approach — GET /stock caps page_size at
// 100 (backend/app/api/v1/stock.py), so a full-store snapshot means paging
// through it, capped the same way the item cache is.
const PAGE_SIZE = 100;
const MAX_CACHE_ITEMS = 1000;

async function fetchFullStock(storeId: string | undefined): Promise<Stock[]> {
  const first = await listStock({ store_id: storeId, page_size: PAGE_SIZE, page: 1 });
  const rows = [...first.items];
  const pagesNeeded = Math.min(Math.ceil(first.total / PAGE_SIZE), Math.ceil(MAX_CACHE_ITEMS / PAGE_SIZE));

  for (let page = 2; page <= pagesNeeded; page++) {
    const next = await listStock({ store_id: storeId, page_size: PAGE_SIZE, page });
    rows.push(...next.items);
  }

  return rows;
}

export interface StockLookup {
  isLoading: boolean;
  /** undefined = not loaded yet (don't warn), not just "0". */
  getQuantity: (itemId: string) => number | undefined;
}

export function useStockLookup(storeId: string | undefined): StockLookup {
  const stockQuery = useQuery({
    queryKey: ["pos-stock-lookup", storeId],
    queryFn: () => fetchFullStock(storeId),
    staleTime: 60_000,
  });

  const byItemId = useMemo(
    () => new Map((stockQuery.data ?? []).map((s) => [s.item_id, s.quantity_on_hand])),
    [stockQuery.data],
  );

  return {
    isLoading: stockQuery.isLoading,
    getQuantity: (itemId: string) => byItemId.get(itemId),
  };
}
