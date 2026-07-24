export type PrinterType = "thermal_58mm" | "thermal_80mm" | "dot_matrix";
export type PrinterConnection = "webusb" | "local_agent";

export interface PrinterProfile {
  id: string;
  tenant_id: string;
  store_id: string;
  name: string;
  type: PrinterType;
  connection: PrinterConnection;
  is_default: boolean;
  paper_width_chars: number;
}

export interface PrinterProfileCreate {
  store_id?: string | null;
  name: string;
  type: PrinterType;
  connection: PrinterConnection;
  is_default?: boolean;
  paper_width_chars: number;
}

export type PrinterProfileUpdate = Partial<PrinterProfileCreate>;
