// Web Bluetooth transport for "bluetooth"-connection printers — reached directly from
// the browser via BLE GATT, no local agent needed. Counterpart to the WebUSB path in
// features/pos/printDispatch.ts. IMPORTANT: Web Bluetooth only speaks BLE (GATT); it
// cannot see "Classic" Bluetooth SPP-only printers. Most ESC/POS thermal printers that
// advertise BLE alongside SPP (dual-mode, e.g. Posiflow/Goojprt/Zjiang-family boards)
// expose one of a small number of well-known vendor "transparent UART" print services
// below — we don't know which one ahead of time, so we request all of them as
// optionalServices and use whichever one the paired device actually implements.
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

// BLE's "Write Without Response" op is capped at the connection's negotiated MTU minus
// ATT header overhead, and Web Bluetooth doesn't expose the negotiated MTU to
// JavaScript, so the safe chunk size can't be known up front. Small chunks + a modest
// inter-chunk delay trades a little speed for a lot less risk of overrunning the
// printer's own onboard receive buffer (a cheap embedded MCU, not a Bluetooth radio
// buffer) — see sendPrintJobViaBluetooth's write loop below.
const INITIAL_CHUNK_SIZE = 100;
const MIN_CHUNK_SIZE = 20;
const CHUNK_DELAY_MS = 8;

export function isWebBluetoothSupported(): boolean {
  return typeof navigator !== "undefined" && "bluetooth" in navigator;
}

interface PairedBluetoothPrinterInfo {
  bluetooth_device_id: string;
  bluetooth_device_name: string;
}

// navigator.bluetooth.getDevices() — the API that would let a print reconnect to a
// previously paired device without re-showing the OS chooser — is still an
// experimental, flag-gated feature in Chrome. We can't depend on it for a POS counter,
// where a cashier printing dozens of bills a shift cannot be expected to click through
// a native device picker every time. Instead, keep the connected BluetoothDevice alive
// in memory for the lifetime of this page/tab — matching how a POS counter is actually
// used, one long session per shift — and only ask to re-pair after an actual page reload.
const sessionPairedDevices = new Map<string, BluetoothDevice>();

// A store's Bill printer is sometimes reprinted from more than one screen (POS +
// Settings test print) within the same session. Cheap BLE printer modules often won't
// accept a fresh connection immediately after a previous one disconnects, so keep the
// GATT connection open and reuse it across every print to that device for the rest of
// the page session instead of disconnecting after each one — faster (skips reconnect +
// service discovery) and avoids that reconnect race entirely.
interface OpenConnection {
  server: BluetoothRemoteGATTServer;
  characteristic: BluetoothRemoteGATTCharacteristic;
}
const openConnections = new Map<string, OpenConnection>();

// Must be called directly from a user gesture (e.g. a button's onClick) — Chrome
// rejects navigator.bluetooth.requestDevice() calls made outside a trusted user
// activation, same rule as WebUSB.
export async function pairBluetoothPrinter(): Promise<PairedBluetoothPrinterInfo> {
  if (!navigator.bluetooth) {
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

  if (navigator.bluetooth?.getDevices) {
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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function connectWithRetry(device: BluetoothDevice, attempts = 4): Promise<BluetoothRemoteGATTServer> {
  if (!device.gatt) {
    throw new Error("This device doesn't expose a Bluetooth GATT connection.");
  }
  let lastErr: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await device.gatt.connect();
    } catch (err) {
      lastErr = err;
      // Cheap BLE printer modules often need a moment after a very recent disconnect
      // (e.g. this same printer just finished a different print job) before they'll
      // accept a new connection — back off and retry instead of failing immediately.
      await sleep(300 * (attempt + 1));
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("Couldn't connect to the Bluetooth printer.");
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
    // Prefer a fire-and-forget ("writeWithoutResponse") characteristic — see
    // writeAll()'s reasoning for why the ACK'd alternative is unusably slow in
    // practice — falling back to an ACK'd-only one if that's all the device exposes.
    const writable =
      characteristics.find((c) => c.properties.writeWithoutResponse) ??
      characteristics.find((c) => c.properties.write);
    if (writable) return writable;
  }
  throw new Error(
    "Connected to the Bluetooth printer, but couldn't find a writable print channel on it — this printer's BLE profile isn't one StoreMate recognizes yet.",
  );
}

async function getConnection(device: BluetoothDevice): Promise<OpenConnection> {
  const existing = openConnections.get(device.id);
  if (existing && existing.server.connected) return existing;

  const server = await connectWithRetry(device);
  const characteristic = await findWritableCharacteristic(server);
  const connection: OpenConnection = { server, characteristic };
  openConnections.set(device.id, connection);
  return connection;
}

async function writeAll(characteristic: BluetoothRemoteGATTCharacteristic, data: Uint8Array): Promise<void> {
  // Fire-and-forget ("Write Without Response") by default — ACK'd writes are
  // dramatically slower on real hardware (a full round-trip per chunk), unusable for a
  // live POS counter. Mitigate the reliability risk instead via smaller chunks + pacing
  // (INITIAL_CHUNK_SIZE/CHUNK_DELAY_MS above), which gives the printer's own onboard
  // buffer time to drain between writes without paying for a full round-trip
  // confirmation on every single chunk.
  const noResponse = characteristic.properties.writeWithoutResponse;
  const write = noResponse
    ? (chunk: Uint8Array) => characteristic.writeValueWithoutResponse(chunk)
    : (chunk: Uint8Array) => characteristic.writeValue(chunk);

  let chunkSize = INITIAL_CHUNK_SIZE;
  let offset = 0;
  while (offset < data.length) {
    const chunk = data.subarray(offset, offset + chunkSize);
    try {
      await write(chunk);
      offset += chunk.length;
      if (offset < data.length) await sleep(CHUNK_DELAY_MS);
    } catch (err) {
      if (chunkSize <= MIN_CHUNK_SIZE) throw err;
      // The negotiated MTU turned out smaller than we optimistically assumed — halve
      // the chunk size and retry this same offset rather than aborting the print.
      chunkSize = Math.max(MIN_CHUNK_SIZE, Math.floor(chunkSize / 2));
    }
  }
}

export async function sendPrintJobViaBluetooth(
  connectionDetails: Record<string, string | undefined>,
  dataBase64: string,
): Promise<void> {
  const deviceId = connectionDetails.bluetooth_device_id;
  if (!deviceId) {
    throw new Error("This printer hasn't been paired yet — go to Settings > Printers and pair it first.");
  }
  const device = await findPairedDevice(deviceId);
  const binary = atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

  const { characteristic } = await getConnection(device);
  try {
    await writeAll(characteristic, bytes);
  } catch (err) {
    // The open connection may now be bad (e.g. the printer dropped mid-write) — evict
    // it so the next print attempts a fresh connect + service discovery instead of
    // repeatedly failing against a stale one.
    openConnections.delete(device.id);
    throw err;
  }
}
