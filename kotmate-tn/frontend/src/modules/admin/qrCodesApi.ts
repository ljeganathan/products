import { api } from "@/lib/api";

export interface TableQrCode {
  id: string;
  table_id: string;
  table_number: string;
  qr_token: string;
  is_active: boolean;
}

export async function getTableQrCode(tableId: string): Promise<TableQrCode | null> {
  const { data } = await api.get<TableQrCode | null>(`/api/v1/tables/${tableId}/qr-code`);
  return data;
}

export async function generateTableQrCode(tableId: string): Promise<TableQrCode> {
  return (await api.post<TableQrCode>(`/api/v1/tables/${tableId}/qr-code`)).data;
}

export interface SectionQrCode {
  id: string;
  section_id: string;
  section_name_en: string;
  qr_token: string;
  is_active: boolean;
}

// Takeaway/Online Delivery QR (Phase 26) — one per (location, section), since
// seating_sections is tenant-wide (a multi-location tenant's one "Takeaway" section is
// shared by every branch) and each branch still needs its own separate code.
export async function getSectionQrCode(
  sectionId: string,
  locationId: string,
): Promise<SectionQrCode | null> {
  const { data } = await api.get<SectionQrCode | null>(`/api/v1/sections/${sectionId}/qr-code`, {
    params: { location_id: locationId },
  });
  return data;
}

export async function generateSectionQrCode(sectionId: string, locationId: string): Promise<SectionQrCode> {
  return (
    await api.post<SectionQrCode>(`/api/v1/sections/${sectionId}/qr-code`, null, {
      params: { location_id: locationId },
    })
  ).data;
}
