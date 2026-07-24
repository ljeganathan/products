import axios from "axios";

import { resolveMediaUrl } from "@/api/client";
import { buildDotMatrixReceipt } from "@/utils/dotmatrix";
import { buildEscPosReceipt, rasterizeLogoToEscPos } from "@/utils/escpos";
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
): Promise<void> {
  const body =
    format === "escpos"
      ? { format, data_base64: bytesToBase64(content as Uint8Array) }
      : { format, data: content as string };
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

/** Picks WebUSB when the profile is thermal and the browser/hardware
 * supports it (desktop Chrome/Edge only, per docs/ARCHITECTURE.md), falling
 * back to the Local Print Agent for everything else — dot-matrix always
 * goes through the agent since it has no browser API path at all. */
export async function dispatchPrint(
  profile: PrinterProfile,
  payload: BillPrintPayload,
): Promise<void> {
  if (profile.type === "dot_matrix") {
    const text = buildDotMatrixReceipt(payload, profile.paper_width_chars);
    await sendToLocalAgent("text", text);
    return;
  }

  const paperWidthDots = profile.type === "thermal_80mm" ? 576 : 384;
  const logoImage = payload.company.logo_url
    ? await loadImage(resolveMediaUrl(payload.company.logo_url))
    : null;
  const logo = logoImage ? rasterizeLogoToEscPos(logoImage, paperWidthDots) : null;
  const bytes = buildEscPosReceipt(payload, {
    paperWidthChars: profile.paper_width_chars,
    paperWidthDots,
    logo,
  });

  if (profile.connection === "webusb" && navigator.usb) {
    try {
      await printViaWebUsb(bytes);
      return;
    } catch (err) {
      console.warn("WebUSB print failed, falling back to Local Print Agent", err);
    }
  }

  await sendToLocalAgent("escpos", bytes);
}
