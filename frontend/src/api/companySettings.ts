import { apiClient } from "@/api/client";
import type { CompanySettings } from "@/types/bill";

export interface CompanySettingsUpdate {
  legal_name?: string;
  display_name?: string;
  address?: string;
  pincode?: string;
  gstin?: string | null;
  fssai_no?: string | null;
  phone?: string | null;
  invoice_footer_text?: string | null;
  show_tamil_item_names?: boolean;
}

export async function getCompanySettings(storeId?: string): Promise<CompanySettings> {
  const { data } = await apiClient.get<CompanySettings>("/settings/company", {
    params: { store_id: storeId },
  });
  return data;
}

export async function updateCompanySettings(
  payload: CompanySettingsUpdate,
  storeId?: string,
): Promise<CompanySettings> {
  const { data } = await apiClient.patch<CompanySettings>("/settings/company", payload, {
    params: { store_id: storeId },
  });
  return data;
}

export async function uploadCompanyLogo(file: File, storeId?: string): Promise<{ logo_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<{ logo_url: string }>(
    "/settings/company/logo",
    formData,
    { params: { store_id: storeId }, headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}
