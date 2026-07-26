import type { BillPrintPayload } from "@/types/bill";
import {
  buildReceiptHeaderLines,
  buildReceiptItemRows,
  buildReceiptTotalsFooterLines,
} from "@/utils/receiptLayout";

const ESC = 0x1b;
const GS = 0x1d;

class EscPosBuilder {
  private bytes: number[] = [];

  init(): this {
    this.bytes.push(ESC, 0x40);
    return this;
  }

  align(mode: 0 | 1 | 2): this {
    this.bytes.push(ESC, 0x61, mode);
    return this;
  }

  bold(on: boolean): this {
    this.bytes.push(ESC, 0x45, on ? 1 : 0);
    return this;
  }

  /** ASCII only — non-ASCII item names (e.g. Tamil) are rasterized as an
   * image instead of routed through this method; see rasterizeTextToEscPos
   * and buildEscPosReceipt below. */
  text(s: string): this {
    for (let i = 0; i < s.length; i++) {
      const code = s.charCodeAt(i);
      this.bytes.push(code < 256 ? code : 0x3f); // '?' fallback for any stray non-ASCII
    }
    return this;
  }

  newline(times = 1): this {
    for (let i = 0; i < times; i++) this.bytes.push(0x0a);
    return this;
  }

  /** GS v 0 raster bit image — used for the company logo. `bitmap` must
   * already be packed 1-bit-per-pixel, MSB first, row-padded to a whole
   * byte (see rasterizeLogoToEscPos). */
  raster(bitmap: Uint8Array, widthBytes: number, height: number): this {
    this.bytes.push(
      GS,
      0x76,
      0x30,
      0x00,
      widthBytes & 0xff,
      (widthBytes >> 8) & 0xff,
      height & 0xff,
      (height >> 8) & 0xff,
    );
    for (const b of bitmap) this.bytes.push(b);
    return this;
  }

  cutPartial(): this {
    this.bytes.push(GS, 0x56, 0x42, 0x00);
    return this;
  }

  build(): Uint8Array {
    return new Uint8Array(this.bytes);
  }
}

/** Thresholds RGBA pixel data into a packed 1-bit-per-pixel ESC/POS raster
 * bitmap (MSB first, row-padded to a whole byte) — shared by logo and
 * rasterized-text rendering below. */
function imageDataToBitmap(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): { bitmap: Uint8Array; widthBytes: number; height: number } {
  const widthBytes = Math.ceil(width / 8);
  const bitmap = new Uint8Array(widthBytes * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      const luminance = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
      const isDark = luminance < 128 && data[idx + 3] > 64;
      if (isDark) {
        const byteIndex = y * widthBytes + Math.floor(x / 8);
        bitmap[byteIndex] |= 0x80 >> x % 8;
      }
    }
  }
  return { bitmap, widthBytes, height };
}

/** Converts an image (already loaded into an HTMLImageElement) into a
 * packed 1-bit ESC/POS raster bitmap, scaled to fit the printer's dot
 * width. Uses simple luminance thresholding — adequate for a logo at
 * thermal-printer resolution. */
export function rasterizeLogoToEscPos(
  image: HTMLImageElement,
  maxWidthPx: number,
): { bitmap: Uint8Array; widthBytes: number; height: number } {
  const scale = Math.min(1, maxWidthPx / image.naturalWidth);
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);
  const { data } = ctx.getImageData(0, 0, width, height);
  return imageDataToBitmap(data, width, height);
}

/** Renders a line of text to a 1-bit raster image via canvas, for item
 * names ESC/POS text mode can't encode (Tamil and other non-ASCII script —
 * see EscPosBuilder.text). The browser's own font stack draws the glyphs
 * correctly (Windows/Chrome ship a Tamil-capable system font), then this
 * bakes that into pixels the printer reproduces regardless of its code
 * page — the same technique already used for the logo above. Untested
 * against real thermal hardware; if a given printer's raster command
 * behaves differently than the logo path already relies on, this would
 * need adjustment. */
export function rasterizeTextToEscPos(
  text: string,
  maxWidthDots: number,
  fontPx = 32,
): { bitmap: Uint8Array; widthBytes: number; height: number } {
  const font = `${fontPx}px "Noto Sans Tamil", "Nirmala UI", sans-serif`;
  const measureCanvas = document.createElement("canvas");
  const measureCtx = measureCanvas.getContext("2d");
  if (!measureCtx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };
  measureCtx.font = font;
  const textWidth = Math.ceil(measureCtx.measureText(text).width);
  const width = Math.max(1, Math.min(maxWidthDots, textWidth + 8));
  const height = Math.ceil(fontPx * 1.4);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#000";
  ctx.font = font;
  ctx.textBaseline = "top";
  ctx.fillText(text, 4, 2, width - 8);

  const { data } = ctx.getImageData(0, 0, width, height);
  return imageDataToBitmap(data, width, height);
}

export interface BuildEscPosOptions {
  paperWidthChars: number;
  /** Printer's addressable dot width — 384 for 58mm, 576 for 80mm at
   * standard 203dpi thermal heads. Only used if `logo` is provided. */
  paperWidthDots?: number;
  logo?: { bitmap: Uint8Array; widthBytes: number; height: number } | null;
}

export function buildEscPosReceipt(payload: BillPrintPayload, options: BuildEscPosOptions): Uint8Array {
  const builder = new EscPosBuilder().init();

  if (options.logo && options.logo.bitmap.length > 0) {
    builder.align(1);
    builder.raster(options.logo.bitmap, options.logo.widthBytes, options.logo.height);
    builder.newline();
  }

  builder.align(1).bold(true).text(payload.company.display_name).bold(false).newline();
  builder.align(0);

  const headerLines = buildReceiptHeaderLines(payload, options.paperWidthChars);
  for (const line of headerLines) {
    // The display_name is already rendered bold above via the logo block.
    if (line.trim() === payload.company.display_name.trim()) continue;
    builder.text(line).newline();
  }

  const paperWidthDots = options.paperWidthDots ?? 384;
  for (const row of buildReceiptItemRows(payload, options.paperWidthChars)) {
    if (row.isNonAscii) {
      const raster = rasterizeTextToEscPos(row.displayName, paperWidthDots);
      if (raster.bitmap.length > 0) {
        builder.raster(raster.bitmap, raster.widthBytes, raster.height);
        builder.newline();
      } else {
        // Canvas unavailable for some reason — fall back to ASCII text
        // rather than silently dropping the line ('?' per non-ASCII char).
        for (const l of row.nameLines) builder.text(l).newline();
      }
    } else {
      for (const l of row.nameLines) builder.text(l).newline();
    }
    builder.text(row.qtyRateLine).newline();
    if (row.discountLine) builder.text(row.discountLine).newline();
  }

  const footerLines = buildReceiptTotalsFooterLines(payload, options.paperWidthChars);
  for (const line of footerLines) builder.text(line).newline();

  builder.newline(3);
  builder.cutPartial();
  return builder.build();
}
