// WebUSB transport for "usb"-connection printers reached from a browser that has no
// local print-agent available (notably Chrome on Android, running on a tablet with a
// USB-OTG-connected thermal printer) — Chrome's WebUSB API talks to the device
// directly, no OS driver required, as long as no other driver has already claimed the
// interface (CLAUDE.md §10). This is the counterpart to lib/printAgent.ts, which
// handles "local_agent" printers on a desktop/laptop counter machine instead.

export function isWebUSBSupported(): boolean {
  return typeof navigator !== "undefined" && "usb" in navigator;
}

interface PairedPrinterInfo {
  usb_vendor_id: number;
  usb_product_id: number;
  usb_product_name?: string;
}

// Must be called directly from a user gesture (e.g. a button's onClick) — Chrome
// rejects navigator.usb.requestDevice() calls made outside a trusted user activation.
export async function pairPrinter(): Promise<PairedPrinterInfo> {
  if (!isWebUSBSupported()) {
    throw new Error("This browser doesn't support WebUSB — use Chrome or Edge.");
  }
  const device = await navigator.usb.requestDevice({ filters: [] });
  return {
    usb_vendor_id: device.vendorId,
    usb_product_id: device.productId,
    usb_product_name: device.productName,
  };
}

async function findPairedDevice(info: PairedPrinterInfo): Promise<USBDevice> {
  const devices = await navigator.usb.getDevices();
  const match = devices.find((d) => d.vendorId === info.usb_vendor_id && d.productId === info.usb_product_id);
  if (!match) {
    throw new Error(
      "This USB printer isn't paired with this browser yet — go to Settings > Printers and pair it first.",
    );
  }
  return match;
}

// Some printers expose their bulk-OUT endpoint on an interface that isn't a strict
// "printer class" (7) interface — take the first interface with a bulk OUT endpoint on
// whichever alternate setting Chrome selected, rather than assuming a fixed layout.
function findBulkOutEndpoint(device: USBDevice): { interfaceNumber: number; endpointNumber: number } {
  for (const iface of device.configuration?.interfaces ?? []) {
    for (const alt of iface.alternates) {
      const out = alt.endpoints.find((e) => e.direction === "out" && e.type === "bulk");
      if (out) return { interfaceNumber: iface.interfaceNumber, endpointNumber: out.endpointNumber };
    }
  }
  throw new Error("This USB device has no printable (bulk OUT) endpoint — is it actually a printer?");
}

const CHUNK_SIZE = 4096;

async function transferAll(device: USBDevice, endpointNumber: number, data: Uint8Array): Promise<void> {
  for (let offset = 0; offset < data.length; offset += CHUNK_SIZE) {
    const chunk = data.subarray(offset, offset + CHUNK_SIZE);
    const result = await device.transferOut(endpointNumber, chunk);
    if (result.status !== "ok") {
      throw new Error(`USB transfer failed (status: ${result.status})`);
    }
  }
}

export async function sendBytesToPairedPrinter(info: PairedPrinterInfo, data: Uint8Array): Promise<void> {
  const device = await findPairedDevice(info);
  await device.open();
  try {
    if (device.configuration === null) {
      await device.selectConfiguration(1);
    }
    const { interfaceNumber, endpointNumber } = findBulkOutEndpoint(device);
    await device.claimInterface(interfaceNumber);
    try {
      await transferAll(device, endpointNumber, data);
    } finally {
      await device.releaseInterface(interfaceNumber);
    }
  } finally {
    await device.close();
  }
}

export async function sendPrintJobViaWebUSB(connectionDetails: Record<string, unknown>, dataBase64: string): Promise<void> {
  const vendorId = Number(connectionDetails.usb_vendor_id);
  const productId = Number(connectionDetails.usb_product_id);
  if (!vendorId || !productId) {
    throw new Error("This printer hasn't been paired yet — go to Settings > Printers and pair it first.");
  }
  const binary = atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  await sendBytesToPairedPrinter({ usb_vendor_id: vendorId, usb_product_id: productId }, bytes);
}
