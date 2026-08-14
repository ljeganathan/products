export type PrinterType = "thermal_58mm" | "thermal_80mm" | "dot_matrix";
export type PrinterConnection = "webusb" | "local_agent" | "network" | "wifi" | "bluetooth" | "rawbt";

/** Connection-specific fields — deliberately unstructured since each
 * connection type needs a different shape and this only ever feeds the
 * frontend print dispatcher, never gets queried on:
 *  - network/wifi: { ip, port }
 *  - bluetooth: { bluetooth_device_id, bluetooth_device_name } */
export type PrinterConnectionDetails = Record<string, string | undefined>;

export interface PrinterProfile {
  id: string;
  tenant_id: string;
  store_id: string;
  name: string;
  type: PrinterType;
  connection: PrinterConnection;
  is_default: boolean;
  paper_width_chars: number;
  connection_details: PrinterConnectionDetails;
}

export interface PrinterProfileCreate {
  store_id?: string | null;
  name: string;
  type: PrinterType;
  connection: PrinterConnection;
  is_default?: boolean;
  paper_width_chars: number;
  connection_details?: PrinterConnectionDetails;
}

export type PrinterProfileUpdate = Partial<PrinterProfileCreate>;
