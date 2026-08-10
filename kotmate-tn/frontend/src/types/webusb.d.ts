// Minimal WebUSB API surface used by lib/webusbPrinter.ts — TypeScript's bundled DOM lib
// doesn't include WebUSB types, and pulling in a whole @types package for four methods
// isn't worth the dependency. Only what we actually call is declared here.

interface USBOutTransferResult {
  status: "ok" | "stall" | "babble";
  bytesWritten: number;
}

interface USBEndpoint {
  endpointNumber: number;
  direction: "in" | "out";
  type: "bulk" | "interrupt" | "isochronous";
}

interface USBAlternateInterface {
  endpoints: USBEndpoint[];
}

interface USBInterface {
  interfaceNumber: number;
  alternates: USBAlternateInterface[];
}

interface USBConfiguration {
  interfaces: USBInterface[];
}

interface USBDevice {
  vendorId: number;
  productId: number;
  productName?: string;
  configuration: USBConfiguration | null;
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(configurationValue: number): Promise<void>;
  claimInterface(interfaceNumber: number): Promise<void>;
  releaseInterface(interfaceNumber: number): Promise<void>;
  transferOut(endpointNumber: number, data: Uint8Array): Promise<USBOutTransferResult>;
}

interface USBDeviceFilter {
  vendorId?: number;
  productId?: number;
  classCode?: number;
}

interface USBDeviceRequestOptions {
  filters: USBDeviceFilter[];
}

interface USB {
  getDevices(): Promise<USBDevice[]>;
  requestDevice(options: USBDeviceRequestOptions): Promise<USBDevice>;
}

interface Navigator {
  readonly usb: USB;
}
