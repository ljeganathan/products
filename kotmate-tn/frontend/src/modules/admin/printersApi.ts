import { api } from "@/lib/api";

export const PRINTER_TARGETS = ["kot", "bill"] as const;
export const PRINTER_TYPES = ["thermal", "dotmatrix"] as const;
export const PRINTER_CONNECTION_TYPES = ["network", "usb", "local_agent"] as const;

export interface Printer {
  id: string;
  location_id: string;
  name: string;
  target: (typeof PRINTER_TARGETS)[number];
  printer_type: (typeof PRINTER_TYPES)[number];
  connection_type: (typeof PRINTER_CONNECTION_TYPES)[number];
  connection_details: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface PrinterCreatePayload {
  location_id: string;
  name: string;
  target: string;
  printer_type: string;
  connection_type: string;
}

export interface PrinterUpdatePayload {
  location_id?: string;
  name?: string;
  target?: string;
  printer_type?: string;
  connection_type?: string;
  is_active?: boolean;
}

export async function listPrinters(): Promise<Printer[]> {
  return (await api.get<Printer[]>("/api/v1/printers")).data;
}

export async function createPrinter(payload: PrinterCreatePayload): Promise<Printer> {
  return (await api.post<Printer>("/api/v1/printers", payload)).data;
}

export async function updatePrinter(id: string, payload: PrinterUpdatePayload): Promise<Printer> {
  return (await api.patch<Printer>(`/api/v1/printers/${id}`, payload)).data;
}
