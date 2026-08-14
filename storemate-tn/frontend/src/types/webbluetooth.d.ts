// Minimal ambient declarations for the Web Bluetooth API subset this app
// uses. Not in TypeScript's default DOM lib (still an experimental/
// Chromium-only API), and there's no first-party @types package worth
// pulling in for the handful of interfaces below — mirrors the same
// approach as types/webhid.d.ts for WebUSB.
interface BluetoothRemoteGATTCharacteristic {
  readonly properties: {
    write: boolean;
    writeWithoutResponse: boolean;
  };
  writeValue(value: BufferSource): Promise<void>;
  writeValueWithoutResponse(value: BufferSource): Promise<void>;
}

interface BluetoothRemoteGATTService {
  getCharacteristics(): Promise<BluetoothRemoteGATTCharacteristic[]>;
}

interface BluetoothRemoteGATTServer {
  readonly connected: boolean;
  connect(): Promise<BluetoothRemoteGATTServer>;
  getPrimaryService(service: string): Promise<BluetoothRemoteGATTService>;
}

interface BluetoothDevice {
  readonly id: string;
  readonly name?: string;
  readonly gatt?: BluetoothRemoteGATTServer;
}

interface BluetoothRequestDeviceOptions {
  acceptAllDevices?: boolean;
  optionalServices?: string[];
}

interface Bluetooth extends EventTarget {
  requestDevice(options: BluetoothRequestDeviceOptions): Promise<BluetoothDevice>;
  getDevices?(): Promise<BluetoothDevice[]>;
}

interface Navigator {
  readonly bluetooth?: Bluetooth;
}
