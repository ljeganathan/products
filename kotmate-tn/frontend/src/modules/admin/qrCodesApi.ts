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
