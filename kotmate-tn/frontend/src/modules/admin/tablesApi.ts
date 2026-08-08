import { api } from "@/lib/api";

export interface Table {
  id: string;
  location_id: string;
  section_id: string;
  table_number: string;
  seating_capacity: number | null;
  status: string;
  is_active: boolean;
  created_at: string;
}

export interface TableCreatePayload {
  location_id: string;
  section_id: string;
  table_number: string;
  seating_capacity?: number | null;
}

export interface TableUpdatePayload extends Partial<TableCreatePayload> {
  is_active?: boolean;
}

export async function listTables(params?: { location_id?: string }): Promise<Table[]> {
  return (await api.get<Table[]>("/api/v1/tables", { params })).data;
}

export async function createTable(payload: TableCreatePayload): Promise<Table> {
  return (await api.post<Table>("/api/v1/tables", payload)).data;
}

export async function updateTable(id: string, payload: TableUpdatePayload): Promise<Table> {
  return (await api.patch<Table>(`/api/v1/tables/${id}`, payload)).data;
}
