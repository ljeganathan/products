import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { listItems, searchPosItems } from "@/api/items";
import { listTaxProfiles } from "@/api/taxProfiles";
import type { PaginatedResponse } from "@/types/common";
import type { Item, TaxProfile } from "@/types/item";

// GET /items caps page_size at 100 (backend/app/api/v1/items.py), so
// building a bigger local cache means paging through it — up to this many
// items total, past which a search falls back to the server (GET
// /pos/items/search) instead of scanning the local cache.
const PAGE_SIZE = 100;
const MAX_CACHE_ITEMS = 1000;

async function fetchFullCatalog(storeId: string | undefined): Promise<PaginatedResponse<Item>> {
  const first = await listItems({ store_id: storeId, page_size: PAGE_SIZE, page: 1 });
  const items = [...first.items];
  const pagesNeeded = Math.min(Math.ceil(first.total / PAGE_SIZE), Math.ceil(MAX_CACHE_ITEMS / PAGE_SIZE));

  for (let page = 2; page <= pagesNeeded; page++) {
    const next = await listItems({ store_id: storeId, page_size: PAGE_SIZE, page });
    items.push(...next.items);
  }

  return { items, total: first.total, page: 1, page_size: items.length };
}

export interface ItemCatalog {
  items: Item[];
  isLoading: boolean;
  isCacheComplete: boolean;
  findByBarcode: (barcode: string) => Item | undefined;
  searchLocal: (query: string, limit?: number) => Item[];
  searchServer: (query: string, limit?: number) => Promise<Item[]>;
  getItem: (itemId: string) => Item | undefined;
  getTaxProfile: (taxProfileId: string) => TaxProfile | undefined;
}

export function useItemCatalog(storeId: string | undefined): ItemCatalog {
  const itemsQuery = useQuery({
    queryKey: ["pos-item-catalog", storeId],
    queryFn: () => fetchFullCatalog(storeId),
    staleTime: 5 * 60_000,
  });
  const taxProfilesQuery = useQuery({
    queryKey: ["pos-tax-profiles", storeId],
    queryFn: listTaxProfiles,
    staleTime: 5 * 60_000,
  });

  const items = useMemo(
    () => itemsQuery.data?.items.filter((i) => i.is_active) ?? [],
    [itemsQuery.data],
  );
  const itemsById = useMemo(() => new Map(items.map((i) => [i.id, i])), [items]);
  const taxProfilesById = useMemo(
    () => new Map((taxProfilesQuery.data ?? []).map((t) => [t.id, t])),
    [taxProfilesQuery.data],
  );
  const isCacheComplete = (itemsQuery.data?.total ?? 0) <= MAX_CACHE_ITEMS;

  function findByBarcode(barcode: string): Item | undefined {
    return items.find((i) => i.barcode === barcode);
  }

  function searchLocal(query: string, limit = 8): Item[] {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return items
      .filter(
        (i) =>
          i.name_en.toLowerCase().includes(q) ||
          i.name_ta.includes(query) ||
          i.sku?.toLowerCase().includes(q) ||
          i.barcode?.includes(query),
      )
      .slice(0, limit);
  }

  async function searchServer(query: string, limit = 8): Promise<Item[]> {
    return searchPosItems(query, storeId, limit);
  }

  return {
    items,
    isLoading: itemsQuery.isLoading || taxProfilesQuery.isLoading,
    isCacheComplete,
    findByBarcode,
    searchLocal,
    searchServer,
    getItem: (itemId: string) => itemsById.get(itemId),
    getTaxProfile: (taxProfileId: string) => taxProfilesById.get(taxProfileId),
  };
}
