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

  /** GS ! n — character size: bits 0-3 = height multiplier-1, bits 4-7 =
   * width multiplier-1. Explicit so the printer's size register can't be
   * left stuck from a previous state — every double-size block below
   * always resets back to `size(0x00)` afterward. */
  size(mode: 0x00 | 0x01 | 0x11): this {
    this.bytes.push(GS, 0x21, mode);
    return this;
  }

  /** ESC 3 0 — zero the line-spacing register. Several common thermal
   * firmwares add the printer's *default* line spacing (~1/6", ESC 2) on
   * top of a raster image's own height when the following LF is
   * processed, which reads as extra blank space after every raster block
   * (logo, rasterized Tamil name, QR code). Pair with lineSpacingDefault()
   * immediately after the image's trailing newline. */
  lineSpacingTight(): this {
    this.bytes.push(ESC, 0x33, 0);
    return this;
  }

  lineSpacingDefault(): this {
    this.bytes.push(ESC, 0x32);
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

export interface RasterBitmap {
  bitmap: Uint8Array;
  widthBytes: number;
  height: number;
}

/** Thresholds RGBA pixel data into a packed 1-bit-per-pixel ESC/POS raster
 * bitmap (MSB first, row-padded to a whole byte) — shared by logo,
 * rasterized-text, and QR-code rendering (see utils/qrRaster.ts). */
export function imageDataToBitmap(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): RasterBitmap {
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

/** Floyd-Steinberg error-diffusion dither into a packed 1-bit-per-pixel
 * ESC/POS raster bitmap — reads far better than a flat luminance threshold
 * for photographic/gradient logo art on a 1-bit thermal head (mirrors PIL's
 * `Image.FLOYDSTEINBERG`, used the same way for the equivalent logo path in
 * KOTMate TN). Deliberately NOT used for text (rasterizeTextToEscPos) or QR
 * codes (utils/qrRaster.ts) — dithering would blur crisp glyph edges and
 * can break a QR code's scannability, both of which need a hard
 * black/white threshold instead (imageDataToBitmap above). Produces the
 * same byte count as the flat-threshold path (still 1 bit/pixel), so this
 * costs nothing extra to transfer over a slow transport like Bluetooth. */
function ditherImageDataToBitmap(data: Uint8ClampedArray, width: number, height: number): RasterBitmap {
  // Float working buffer so diffused error doesn't clip/truncate between
  // pixels — transparent source pixels are treated as white background,
  // matching imageDataToBitmap's `alpha > 64` gate.
  const gray = new Float32Array(width * height);
  for (let i = 0; i < width * height; i++) {
    const idx = i * 4;
    const luminance = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
    gray[i] = data[idx + 3] > 64 ? luminance : 255;
  }

  const widthBytes = Math.ceil(width / 8);
  const bitmap = new Uint8Array(widthBytes * height);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      const isDark = gray[i] < 128;
      if (isDark) bitmap[y * widthBytes + Math.floor(x / 8)] |= 0x80 >> x % 8;

      const error = gray[i] - (isDark ? 0 : 255);
      if (x + 1 < width) gray[i + 1] += (error * 7) / 16;
      if (y + 1 < height) {
        if (x > 0) gray[i + width - 1] += (error * 3) / 16;
        gray[i + width] += (error * 5) / 16;
        if (x + 1 < width) gray[i + width + 1] += (error * 1) / 16;
      }
    }
  }

  return { bitmap, widthBytes, height };
}

// Sanity cap only (~50mm at 203dpi), mirrors KOTMate TN's
// render_logo_to_escpos max_height_px — takes over as the limiting
// dimension for an unusually narrow/tall source logo instead of letting
// fit-to-width stretch it into an excessively long print.
const LOGO_MAX_HEIGHT_DOTS = 400;

/** Converts an image (already loaded into an HTMLImageElement) into a
 * packed 1-bit ESC/POS raster bitmap, using Floyd-Steinberg dithering (see
 * above) — appropriate for a logo's continuous-tone art, unlike the flat
 * threshold used for text/QR. Always scaled to *fill* `maxWidthPx`
 * (upscaling a small source image if needed, not just downscaling a large
 * one) — a logo printed smaller than the paper is wasted header space on a
 * receipt, same reasoning as KOTMate TN's equivalent renderer. */
export function rasterizeLogoToEscPos(image: HTMLImageElement, maxWidthPx: number): RasterBitmap {
  let scale = maxWidthPx / image.naturalWidth;
  if (image.naturalHeight * scale > LOGO_MAX_HEIGHT_DOTS) {
    scale = LOGO_MAX_HEIGHT_DOTS / image.naturalHeight;
  }
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
  return ditherImageDataToBitmap(data, width, height);
}

/** Renders a line of text to a 1-bit raster image via canvas, for item
 * names ESC/POS text mode can't encode (Tamil and other non-ASCII script —
 * see EscPosBuilder.text). The browser's own font stack draws the glyphs
 * correctly (Windows/Chrome ship a Tamil-capable system font, and canvas
 * fillText shapes complex-script ligatures/vowel-sign repositioning
 * correctly via the OS text layout engine), then this bakes that into
 * pixels the printer reproduces regardless of its code page — the same
 * technique already used for the logo above.
 *
 * Padded just 1px on every side and sized to the text's *actual* glyph
 * bounding box (not a fixed font-size multiple) — this renders inline
 * between/among ordinary ESC/POS text lines (bilingual item rows), so it
 * needs to read as one compact line rather than leave a visible gap.
 * Mirrors KOTMate TN's tamil_raster.py, which found the same tuning
 * necessary (its docstring: "should read as 'one compact line'").
 *
 * `fontPx` defaults to 24 — the same size KOTMate TN's renderer uses,
 * tuned to sit close to a thermal printer's native Font A cell height
 * (~24 dots) rather than dwarfing the plain-ASCII lines around it. */
export function rasterizeTextToEscPos(
  text: string,
  maxWidthDots: number,
  fontPx = 24,
): { bitmap: Uint8Array; widthBytes: number; height: number } {
  const font = `${fontPx}px "Noto Sans Tamil", "Nirmala UI", sans-serif`;
  const measureCanvas = document.createElement("canvas");
  const measureCtx = measureCanvas.getContext("2d");
  if (!measureCtx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };
  measureCtx.font = font;
  const metrics = measureCtx.measureText(text);
  const textWidth = Math.ceil(metrics.width);
  const ascent = Math.ceil(metrics.actualBoundingBoxAscent || fontPx * 0.8);
  const descent = Math.ceil(metrics.actualBoundingBoxDescent || fontPx * 0.2);
  const width = Math.max(1, Math.min(maxWidthDots, textWidth + 2));
  const height = Math.max(1, ascent + descent) + 2;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#000";
  ctx.font = font;
  ctx.textBaseline = "alphabetic";
  ctx.fillText(text, 1, 1 + ascent, width - 2);

  const { data } = ctx.getImageData(0, 0, width, height);
  return imageDataToBitmap(data, width, height);
}

export interface BuildEscPosOptions {
  paperWidthChars: number;
  /** Printer's addressable dot width — 384 for 58mm, 576 for 80mm at
   * standard 203dpi thermal heads. Only used if `logo`/`qr` is provided. */
  paperWidthDots?: number;
  logo?: RasterBitmap | null;
  /** UPI QR code raster, built by utils/qrRaster.ts from the company's
   * `upi_vpa` + this bill's amount — printed centered above the cut, after
   * the totals footer. */
  qr?: RasterBitmap | null;
}

/** Emits a raster image wrapped in tight line-spacing (see
 * EscPosBuilder.lineSpacingTight) so the trailing newline advances by
 * exactly the image's own height instead of the printer's default line
 * spacing stacking on top of it. */
function emitRaster(builder: EscPosBuilder, raster: RasterBitmap): void {
  builder.lineSpacingTight();
  builder.raster(raster.bitmap, raster.widthBytes, raster.height);
  builder.newline();
  builder.lineSpacingDefault();
}

export function buildEscPosReceipt(payload: BillPrintPayload, options: BuildEscPosOptions): Uint8Array {
  const builder = new EscPosBuilder().init();
  const hasLogo = Boolean(options.logo && options.logo.bitmap.length > 0);

  builder.align(1);
  if (hasLogo && options.logo) {
    emitRaster(builder, options.logo);
  } else {
    // A logo image (when present) may already have the company name baked
    // into its artwork, so the two are mutually exclusive rather than
    // printing both — this text fallback carries the double-size/bold
    // emphasis a logo would otherwise provide.
    builder.bold(true).size(0x11).text(payload.company.display_name).size(0x00).bold(false).newline();
  }
  builder.align(0);

  const headerLines = buildReceiptHeaderLines(payload, options.paperWidthChars);
  for (const line of headerLines) {
    // The display_name is already rendered above (logo or text fallback).
    if (line.trim() === payload.company.display_name.trim()) continue;
    builder.text(line).newline();
  }

  const paperWidthDots = options.paperWidthDots ?? 384;
  for (const row of buildReceiptItemRows(payload, options.paperWidthChars)) {
    if (row.isNonAscii) {
      const raster = rasterizeTextToEscPos(row.displayName, paperWidthDots);
      if (raster.bitmap.length > 0) {
        emitRaster(builder, raster);
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
  for (const line of footerLines) {
    // The TOTAL row is the one line worth visually emphasizing on the
    // printed copy — matches the same "Grand Total" double-height/bold
    // treatment KOTMate TN's thermal template uses. Detected by its fixed
    // "TOTAL" prefix (twoCol("TOTAL", ...) always starts the line with it)
    // rather than restructuring the footer builder shared with the
    // preview/dot-matrix renderers, which can't render size changes anyway.
    if (line.startsWith("TOTAL")) {
      builder.bold(true).size(0x01).text(line).size(0x00).bold(false).newline();
    } else {
      builder.text(line).newline();
    }
  }

  if (options.qr && options.qr.bitmap.length > 0) {
    builder.newline();
    builder.align(1);
    emitRaster(builder, options.qr);
    builder.text("Scan to pay via UPI").newline();
    builder.align(0);
  }

  builder.newline(3);
  builder.cutPartial();
  return builder.build();
}
