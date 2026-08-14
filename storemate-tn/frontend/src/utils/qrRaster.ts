import QRCode from "qrcode";

import { imageDataToBitmap, type RasterBitmap } from "@/utils/escpos";
import { paiseToPlainAmount } from "@/utils/money";

/** Builds the UPI deep-link URI a payment app scans and opens directly —
 * `am`/`tn` (amount/transaction note) are optional per the UPI spec but
 * included so the customer's app pre-fills the exact bill amount. */
export function buildUpiUri(vpa: string, payeeName: string, amountPaise: number, billNumber: number): string {
  const params = new URLSearchParams({
    pa: vpa,
    pn: payeeName,
    am: paiseToPlainAmount(amountPaise),
    cu: "INR",
    tn: `Bill ${billNumber}`,
  });
  return `upi://pay?${params.toString()}`;
}

/** Renders a UPI payment URI to a 1-bit ESC/POS raster bitmap via canvas —
 * same rasterize-to-canvas-then-threshold technique already used for the
 * logo and Tamil item names in escpos.ts, so it prints correctly regardless
 * of the printer's own code page (a QR code is inherently graphics, not
 * text, so there's no non-raster path here). Returns `null` if canvas is
 * unavailable, matching the other rasterizers' fallback contract. */
export async function buildUpiQrEscPos(upiUri: string, maxWidthDots: number): Promise<RasterBitmap | null> {
  const size = Math.max(64, Math.min(maxWidthDots, 300));
  const canvas = document.createElement("canvas");
  await QRCode.toCanvas(canvas, upiUri, { width: size, margin: 1, errorCorrectionLevel: "M" });
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return imageDataToBitmap(data, canvas.width, canvas.height);
}
