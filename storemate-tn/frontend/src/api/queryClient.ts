import { QueryClient } from "@tanstack/react-query";

// staleTime is deliberately generous: item/category/tax-profile master data
// (Phase 3 APIs) changes rarely relative to how often the POS search (Phase
// 5) will hit it, so we favor cache hits over refetch churn by default.
// Screens with fast-changing data (stock levels, bills) should override
// staleTime per-query rather than lowering this global default.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
