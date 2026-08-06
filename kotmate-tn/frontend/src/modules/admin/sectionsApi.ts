import { api } from "@/lib/api";

export interface Section {
  id: string;
  name_en: string;
  name_ta: string | null;
  is_seating: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface SectionCreatePayload {
  name_en: string;
  name_ta?: string;
  is_seating?: boolean;
  display_order?: number;
}

export interface SectionUpdatePayload {
  name_en?: string;
  name_ta?: string;
  is_seating?: boolean;
  display_order?: number;
  is_active?: boolean;
}

export async function listSections(): Promise<Section[]> {
  return (await api.get<Section[]>("/api/v1/sections")).data;
}

export async function createSection(payload: SectionCreatePayload): Promise<Section> {
  return (await api.post<Section>("/api/v1/sections", payload)).data;
}

export async function updateSection(id: string, payload: SectionUpdatePayload): Promise<Section> {
  return (await api.patch<Section>(`/api/v1/sections/${id}`, payload)).data;
}

export async function reorderSections(entries: { id: string; display_order: number }[]): Promise<Section[]> {
  return (await api.put<Section[]>("/api/v1/sections/reorder", { sections: entries })).data;
}
