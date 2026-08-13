// Minimal Web Bluetooth API surface used by lib/webBluetoothPrinter.ts — TypeScript's
// bundled DOM lib doesn't include Web Bluetooth types, and pulling in a whole @types
// package for a handful of methods isn't worth the dependency. Only what we actually
// call is declared here (mirrors types/webusb.d.ts's approach).

interface BluetoothCharacteristicProperties {
  write: boolean;
  writeWithoutResponse: boolean;
}

interface BluetoothRemoteGATTCharacteristic {
  properties: BluetoothCharacteristicProperties;
  writeValue(data: Uint8Array): Promise<void>;
  writeValueWithoutResponse(data: Uint8Array): Promise<void>;
}

interface BluetoothRemoteGATTService {
  getCharacteristics(): Promise<BluetoothRemoteGATTCharacteristic[]>;
}

interface BluetoothRemoteGATTServer {
  readonly connected: boolean;
  connect(): Promise<BluetoothRemoteGATTServer>;
  disconnect(): void;
  getPrimaryService(service: string): Promise<BluetoothRemoteGATTService>;
}

interface BluetoothDevice {
  id: string;
  name?: string;
  gatt?: BluetoothRemoteGATTServer;
}

interface BluetoothRequestDeviceFilter {
  services?: string[];
  namePrefix?: string;
}

interface BluetoothRequestDeviceOptions {
  filters?: BluetoothRequestDeviceFilter[];
  acceptAllDevices?: boolean;
  optionalServices?: string[];
}

interface Bluetooth {
  getDevices?(): Promise<BluetoothDevice[]>;
  requestDevice(options: BluetoothRequestDeviceOptions): Promise<BluetoothDevice>;
}

interface Navigator {
  readonly bluetooth: Bluetooth;
}
