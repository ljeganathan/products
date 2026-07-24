import { apiClient } from "@/api/client";
import type { TaxProfile, TaxProfileCreate, TaxProfileUpdate } from "@/types/item";

export async function listTaxProfiles(): Promise<TaxProfile[]> {
  const { data } = await apiClient.get<TaxProfile[]>("/settings/tax-profiles");
  return data;
}

export async function createTaxProfile(payload: TaxProfileCreate): Promise<TaxProfile> {
  const { data } = await apiClient.post<TaxProfile>("/settings/tax-profiles", payload);
  return data;
}

export async function updateTaxProfile(
  id: string,
  payload: TaxProfileUpdate,
): Promise<TaxProfile> {
  const { data } = await apiClient.patch<TaxProfile>(`/settings/tax-profiles/${id}`, payload);
  return data;
}

export async function deleteTaxProfile(id: string): Promise<void> {
  await apiClient.delete(`/settings/tax-profiles/${id}`);
}
