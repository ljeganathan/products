import { api } from "@/lib/api";

export interface HotelMaster {
  id: string | null;
  location_id: string;
  name: string | null;
  door_no: string | null;
  street: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  phone: string | null;
  gstin: string | null;
  logo_url: string | null;
  upi_id: string | null;
  show_tamil_names: boolean;
  gstin_state_warning: string | null;
  created_at: string | null;
}

export interface HotelMasterUpdatePayload {
  location_id: string;
  name: string;
  door_no?: string | null;
  street?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  pincode?: string | null;
  phone?: string | null;
  gstin?: string | null;
  upi_id?: string | null;
  show_tamil_names: boolean;
}

export async function getHotelMaster(locationId: string): Promise<HotelMaster> {
  return (
    await api.get<HotelMaster>("/api/v1/settings/hotel-master", { params: { location_id: locationId } })
  ).data;
}

export async function saveHotelMaster(payload: HotelMasterUpdatePayload): Promise<HotelMaster> {
  return (await api.put<HotelMaster>("/api/v1/settings/hotel-master", payload)).data;
}

export async function uploadHotelMasterLogo(locationId: string, file: File): Promise<HotelMaster> {
  const form = new FormData();
  form.append("file", file);
  return (
    await api.post<HotelMaster>(`/api/v1/settings/hotel-master/${locationId}/logo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  ).data;
}
