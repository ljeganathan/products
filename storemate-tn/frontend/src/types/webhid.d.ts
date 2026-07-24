// Minimal ambient declarations for the WebUSB API subset this app uses.
// Not in TypeScript's default DOM lib (still an experimental/Chromium-only
// API), and there's no first-party @types package worth pulling in for
// three method signatures.
interface USBDevice {
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(configurationValue: number): Promise<void>;
  claimInterface(interfaceNumber: number): Promise<void>;
  transferOut(endpointNumber: number, data: BufferSource): Promise<{ status: string; bytesWritten: number }>;
  configuration: { interfaces: { interfaceNumber: number; alternate: { endpoints: { endpointNumber: number; direction: string }[] } }[] } | null;
}

interface USBRequestDeviceOptions {
  filters: { vendorId?: number; productId?: number }[];
}

interface USB extends EventTarget {
  requestDevice(options: USBRequestDeviceOptions): Promise<USBDevice>;
  getDevices(): Promise<USBDevice[]>;
}

interface Navigator {
  readonly usb?: USB;
}
