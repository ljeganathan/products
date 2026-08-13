// Web Bluetooth transport for "bluetooth"-connection printers — reached directly from
// the browser via BLE GATT, no local agent needed (CLAUDE.md §10). Counterpart to
// lib/webusbPrinter.ts. IMPORTANT: Web Bluetooth only speaks BLE (GATT); it cannot see
// "Classic" Bluetooth SPP-only printers. Most ESC/POS thermal printers that advertise
// BLE alongside SPP (dual-mode, e.g. Posiflow/Goojprt/Zjiang-family boards) expose one
// of a small number of well-known vendor "transparent UART" print services below — we
// don't know which one ahead of time, so we request all of them as optionalServices
// and use whichever one the paired device actually implements.
const CANDIDATE_SERVICES = [
  // Zjiang/Goojprt-family "print service" — very common in rebranded ESC/POS BLE
  // thermal printers sold under many brand names (incl. Posiflow-style KPxxx boards).
  "000018f0-0000-1000-8000-00805f9b34fb",
  // ISSC/HM-10-style "transparent UART" service — the other common cheap-BLE-module
  // profile these printers are frequently built on.
  "49535343-fe7d-4ae5-8fa9-9fafd205e455",
  // Nordic UART Service (NUS) — seen on some Nordic-chipset printer boards.
  "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
] as const;

// Small enough to stay under the default (unnegotiated) 23-byte ATT MTU's ~20-byte
// payload on every platform — Chrome/Android will use a larger MTU when the device
// negotiates one, but there's no portable way to query it beforehand, and 20 bytes is
// safe everywhere at the cost of a slightly slower print.
const CHUNK_SIZE = 20;
const CHUNK_DELAY_MS = 15;

export function isWebBluetoothSupported(): boolean {
  return typeof navigator !== "undefined" && "bluetooth" in navigator;
}

interface PairedBluetoothPrinterInfo {
  bluetooth_device_id: string;
  bluetooth_device_name: string;
}

// navigator.bluetooth.getDevices() — the API that would let a print reconnect to a
// previously paired device without re-showing the OS chooser — is still an
// experimental, flag-gated feature in Chrome (not on by default on desktop, and not
// reliably present on Android either; confirmed absent in current stable testing). We
// can't depend on it for a POS counter, where a cashier printing dozens of bills a
// shift cannot be expected to click through a native device picker every time.
// Instead, keep the connected BluetoothDevice alive in memory for the lifetime of this
// page/tab — which matches how a POS counter is actually used, one long session per
// shift (CLAUDE.md §9) — and only ask to re-pair after an actual page reload.
const sessionPairedDevices = new Map<string, BluetoothDevice>();

// Must be called directly from a user gesture (e.g. a button's onClick) — Chrome
// rejects navigator.bluetooth.requestDevice() calls made outside a trusted user
// activation, same rule as WebUSB.
export async function pairBluetoothPrinter(): Promise<PairedBluetoothPrinterInfo> {
  if (!isWebBluetoothSupported()) {
    throw new Error("This browser doesn't support Web Bluetooth — use Chrome on desktop or Android.");
  }
  const device = await navigator.bluetooth.requestDevice({
    acceptAllDevices: true,
    optionalServices: [...CANDIDATE_SERVICES],
  });
  sessionPairedDevices.set(device.id, device);
  return {
    bluetooth_device_id: device.id,
    bluetooth_device_name: device.name ?? "Bluetooth printer",
  };
}

async function findPairedDevice(deviceId: string): Promise<BluetoothDevice> {
  const cached = sessionPairedDevices.get(deviceId);
  if (cached) return cached;

  if (navigator.bluetooth.getDevices) {
    const devices = await navigator.bluetooth.getDevices();
    const match = devices.find((d) => d.id === deviceId);
    if (match) {
      sessionPairedDevices.set(match.id, match);
      return match;
    }
  }

  throw new Error(
    "This Bluetooth printer needs to be re-paired — go to Settings > Printers and tap Re-pair Printer (this browser doesn't keep a Bluetooth pairing across a page reload).",
  );
}

async function findWritableCharacteristic(
  server: BluetoothRemoteGATTServer,
): Promise<BluetoothRemoteGATTCharacteristic> {
  for (const serviceUuid of CANDIDATE_SERVICES) {
    let service: BluetoothRemoteGATTService;
    try {
      service = await server.getPrimaryService(serviceUuid);
    } catch {
      continue; // this device doesn't implement this candidate service — try the next
    }
    const characteristics = await service.getCharacteristics();
    const writable = characteristics.find((c) => c.properties.write || c.properties.writeWithoutResponse);
    if (writable) return writable;
  }
  throw new Error(
    "Connected to the Bluetooth printer, but couldn't find a writable print channel on it — this printer's BLE profile isn't one KOTMate recognizes yet.",
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function writeAll(characteristic: BluetoothRemoteGATTCharacteristic, data: Uint8Array): Promise<void> {
  const canWriteWithoutResponse = characteristic.properties.writeWithoutResponse;
  for (let offset = 0; offset < data.length; offset += CHUNK_SIZE) {
    const chunk = data.subarray(offset, offset + CHUNK_SIZE);
    if (canWriteWithoutResponse) {
      await characteristic.writeValueWithoutResponse(chunk);
    } else {
      await characteristic.writeValue(chunk);
    }
    await sleep(CHUNK_DELAY_MS);
  }
}

export async function sendPrintJobViaBluetooth(
  connectionDetails: Record<string, unknown>,
  dataBase64: string,
): Promise<void> {
  const deviceId = connectionDetails.bluetooth_device_id;
  if (typeof deviceId !== "string" || !deviceId) {
    throw new Error("This printer hasn't been paired yet — go to Settings > Printers and pair it first.");
  }
  const device = await findPairedDevice(deviceId);
  if (!device.gatt) {
    throw new Error("This device doesn't expose a Bluetooth GATT connection.");
  }
  const binary = atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

  const server = await device.gatt.connect();
  try {
    const characteristic = await findWritableCharacteristic(server);
    await writeAll(characteristic, bytes);
  } finally {
    server.disconnect();
  }
}
