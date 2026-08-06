import { api } from "@/lib/api";

export interface TaxRule {
  id: string;
  name: string;
  cgst_rate: number;
  sgst_rate: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
}

export interface TaxRuleCreatePayload {
  name: string;
  cgst_rate: number;
  sgst_rate: number;
  is_default?: boolean;
}

export interface TaxRuleUpdatePayload {
  name?: string;
  cgst_rate?: number;
  sgst_rate?: number;
  is_default?: boolean;
  is_active?: boolean;
}

export async function listTaxRules(): Promise<TaxRule[]> {
  return (await api.get<TaxRule[]>("/api/v1/tax-rules")).data;
}

export async function createTaxRule(payload: TaxRuleCreatePayload): Promise<TaxRule> {
  return (await api.post<TaxRule>("/api/v1/tax-rules", payload)).data;
}

export async function updateTaxRule(id: string, payload: TaxRuleUpdatePayload): Promise<TaxRule> {
  return (await api.patch<TaxRule>(`/api/v1/tax-rules/${id}`, payload)).data;
}
