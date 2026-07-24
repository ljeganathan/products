import { apiClient } from "@/api/client";
import type { PaginatedResponse } from "@/types/common";
import type { Stock, StockAdjustRequest, StockMovement } from "@/types/stock";

export interface ListStockParams {
  page?: number;
  page_size?: number;
  store_id?: string;
}

export async function listStock(params: ListStockParams = {}): Promise<PaginatedResponse<Stock>> {
  const { data } = await apiClient.get<PaginatedResponse<Stock>>("/stock", { params });
  return data;
}

export async function listLowStock(params: ListStockParams = {}): Promise<PaginatedResponse<Stock>> {
  const { data } = await apiClient.get<PaginatedResponse<Stock>>("/stock/low-stock", { params });
  return data;
}

export async function adjustStock(payload: StockAdjustRequest): Promise<Stock> {
  const { data } = await apiClient.post<Stock>("/stock/adjust", payload);
  return data;
}

export interface ListMovementsParams {
  page?: number;
  page_size?: number;
  item_id?: string;
}

export async function listStockMovements(
  params: ListMovementsParams = {},
): Promise<PaginatedResponse<StockMovement>> {
  const { data } = await apiClient.get<PaginatedResponse<StockMovement>>("/stock/movements", {
    params,
  });
  return data;
}
