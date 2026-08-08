import { api } from "@/lib/api";

export const PRINTER_TARGETS = ["kot", "bill"] as const;
export const PRINTER_TYPES = ["thermal", "dotmatrix"] as const;
export const PRINTER_CONNECTION_TYPES = ["network", "usb", "local_agent", "wifi", "bluetooth"] as const;
// 58/80mm thermal roll widths, 241mm (9.5") dot-matrix continuous stationery — a "Custom"
// option in the UI falls back to a free-entry mm field for anything else (CLAUDE.md §10).
export const PRINTER_PAPER_WIDTHS_MM = [58, 80, 241] as const;

export interface Printer {
  id: string;
  location_id: string;
  name: string;
  target: (typeof PRINTER_TARGETS)[number];
  printer_type: (typeof PRINTER_TYPES)[number];
  connection_type: (typeof PRINTER_CONNECTION_TYPES)[number];
  connection_details: Record<string, unknown>;
  paper_width_mm: number | null;
  is_active: boolean;
  created_at: string;
}

export interface PrinterCreatePayload {
  location_id: string;
  name: string;
  target: string;
  printer_type: string;
  connection_type: string;
  connection_details?: Record<string, unknown>;
  paper_width_mm?: number | null;
}

export interface PrinterUpdatePayload {
  location_id?: string;
  name?: string;
  target?: string;
  printer_type?: string;
  connection_type?: string;
  connection_details?: Record<string, unknown>;
  paper_width_mm?: number | null;
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
