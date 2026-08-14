import axios from "axios";

import { resolveMediaUrl } from "@/api/client";
import { printPrinterProfileViaNetwork } from "@/api/printerProfiles";
import { buildDotMatrixReceipt } from "@/utils/dotmatrix";
import { buildEscPosReceipt, rasterizeLogoToEscPos } from "@/utils/escpos";
import { buildUpiQrEscPos, buildUpiUri } from "@/utils/qrRaster";
import { sendPrintJobViaRawbt } from "@/utils/rawbtPrinter";
import { sendPrintJobViaBluetooth } from "@/utils/webBluetoothPrinter";
import type { BillPrintPayload } from "@/types/bill";
import type { PrinterProfile } from "@/types/printer";

const LOCAL_PRINT_AGENT_URL =
  import.meta.env.VITE_LOCAL_PRINT_AGENT_URL ?? "http://localhost:9743";

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

async function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

async function sendToLocalAgent(
  format: "escpos" | "text",
  content: Uint8Array | string,
  printerName?: string,
): Promise<void> {
  const body = {
    ...(format === "escpos"
      ? { format, data_base64: bytesToBase64(content as Uint8Array) }
      : { format, data: content as string }),
    // Optional — the agent falls back to its own --printer default (or the
    // machine's Windows default printer) when omitted, so this only needs
    // setting when a till PC has more than one printer queue registered.
    ...(printerName ? { printer_name: printerName } : {}),
  };
  await axios.post(`${LOCAL_PRINT_AGENT_URL}/print`, body, { timeout: 5_000 });
}

async function printViaWebUsb(bytes: Uint8Array): Promise<void> {
  if (!navigator.usb) throw new Error("WebUSB not available in this browser");
  const devices = await navigator.usb.getDevices();
  const device = devices[0] ?? (await navigator.usb.requestDevice({ filters: [] }));

  await device.open();
  if (device.configuration === null) await device.selectConfiguration(1);
  const iface = device.configuration?.interfaces[0];
  if (!iface) throw new Error("No USB interface found on printer");
  await device.claimInterface(iface.interfaceNumber);

  const outEndpoint = iface.alternate.endpoints.find((e) => e.direction === "out");
  if (!outEndpoint) throw new Error("No OUT endpoint found on printer");

  await device.transferOut(outEndpoint.endpointNumber, bytes);
  await device.close();
}

/** Dispatches already-built ESC/POS bytes (thermal profiles only — dot-matrix
 * is handled inline in dispatchPrint below) to whichever transport the
 * profile's `connection` names: network/wifi go via the backend (raw TCP
 * socket, browsers can't open one directly), bluetooth via Web Bluetooth
 * GATT, rawbt via an Android intent: URL, webusb direct from the browser
 * (falling back to the Local Print Agent if unavailable/fails), and
 * local_agent via the Local Print Agent directly. */
async function sendEscPosBytes(profile: PrinterProfile, bytes: Uint8Array): Promise<void> {
  switch (profile.connection) {
    case "network":
    case "wifi":
      await printPrinterProfileViaNetwork(profile.id, bytesToBase64(bytes));
      return;
    case "bluetooth":
      await sendPrintJobViaBluetooth(profile.connection_details, bytesToBase64(bytes));
      return;
    case "rawbt":
      await sendPrintJobViaRawbt(bytesToBase64(bytes));
      return;
    case "webusb":
      if (navigator.usb) {
        try {
          await printViaWebUsb(bytes);
          return;
        } catch (err) {
          console.warn("WebUSB print failed, falling back to Local Print Agent", err);
        }
      }
      await sendToLocalAgent("escpos", bytes, profile.connection_details.windows_printer_name);
      return;
    default:
      await sendToLocalAgent("escpos", bytes, profile.connection_details.windows_printer_name);
  }
}

export async function dispatchPrint(
  profile: PrinterProfile,
  payload: BillPrintPayload,
): Promise<void> {
  if (profile.type === "dot_matrix") {
    const text = buildDotMatrixReceipt(payload, profile.paper_width_chars);
    if (profile.connection === "network" || profile.connection === "wifi") {
      await printPrinterProfileViaNetwork(profile.id, bytesToBase64(new TextEncoder().encode(text)));
      return;
    }
    await sendToLocalAgent("text", text, profile.connection_details.windows_printer_name);
    return;
  }

  const paperWidthDots = profile.type === "thermal_80mm" ? 576 : 384;
  const logoImage = payload.company.logo_url
    ? await loadImage(resolveMediaUrl(payload.company.logo_url))
    : null;
  const logo = logoImage ? rasterizeLogoToEscPos(logoImage, paperWidthDots) : null;

  // Scan-to-pay only makes sense when the customer is actually paying via
  // UPI at the counter — a cash/card sale showing the same QR would invite
  // a second, unintended payment.
  const qr =
    payload.company.show_upi_qr && payload.company.upi_vpa && payload.payment_mode === "upi"
      ? await buildUpiQrEscPos(
          buildUpiUri(payload.company.upi_vpa, payload.company.display_name, payload.total_paise, payload.bill_number),
          paperWidthDots,
        )
      : null;

  const bytes = buildEscPosReceipt(payload, {
    paperWidthChars: profile.paper_width_chars,
    paperWidthDots,
    logo,
    qr,
  });

  await sendEscPosBytes(profile, bytes);
}
