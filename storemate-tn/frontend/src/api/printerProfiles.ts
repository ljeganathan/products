import { apiClient } from "@/api/client";
import type { PrinterProfile, PrinterProfileCreate, PrinterProfileUpdate } from "@/types/printer";

export async function listPrinterProfiles(storeId?: string): Promise<PrinterProfile[]> {
  const { data } = await apiClient.get<PrinterProfile[]>("/settings/printer-profiles", {
    params: { store_id: storeId },
  });
  return data;
}

export async function createPrinterProfile(
  payload: PrinterProfileCreate,
): Promise<PrinterProfile> {
  const { data } = await apiClient.post<PrinterProfile>("/settings/printer-profiles", payload);
  return data;
}

export async function updatePrinterProfile(
  id: string,
  payload: PrinterProfileUpdate,
): Promise<PrinterProfile> {
  const { data } = await apiClient.patch<PrinterProfile>(
    `/settings/printer-profiles/${id}`,
    payload,
  );
  return data;
}

export async function deletePrinterProfile(id: string): Promise<void> {
  await apiClient.delete(`/settings/printer-profiles/${id}`);
}

/** Network/WiFi printers are reached over a raw TCP socket, which browser
 * JavaScript can't open — the backend opens it instead (see
 * backend/app/utils/network_print.py). `dataBase64` is the already-built
 * ESC/POS (or dot-matrix text) job, same bytes WebUSB/local-agent would send. */
export async function printPrinterProfileViaNetwork(id: string, dataBase64: string): Promise<void> {
  await apiClient.post(`/settings/printer-profiles/${id}/print-network`, { data_base64: dataBase64 });
}
