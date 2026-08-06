import { api } from "@/lib/api";

export interface LocationOption {
  id: string;
  name: string;
}

export interface LocationDetail {
  id: string;
  name: string;
  door_no: string | null;
  street: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LocationCreatePayload {
  name: string;
  door_no?: string | null;
  street?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  pincode?: string | null;
  phone?: string | null;
}

export interface LocationUpdatePayload extends Partial<LocationCreatePayload> {
  is_active?: boolean;
}

export async function listLocations(): Promise<LocationOption[]> {
  return (await api.get<LocationOption[]>("/api/v1/locations")).data;
}

export async function listManagedLocations(): Promise<LocationDetail[]> {
  return (await api.get<LocationDetail[]>("/api/v1/locations/manage")).data;
}

export async function createLocation(payload: LocationCreatePayload): Promise<LocationDetail> {
  return (await api.post<LocationDetail>("/api/v1/locations", payload)).data;
}

export async function updateLocation(id: string, payload: LocationUpdatePayload): Promise<LocationDetail> {
  return (await api.patch<LocationDetail>(`/api/v1/locations/${id}`, payload)).data;
}
