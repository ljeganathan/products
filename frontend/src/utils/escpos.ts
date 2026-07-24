import type { BillPrintPayload } from "@/types/bill";
import { buildReceiptLines } from "@/utils/receiptLayout";

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

  /** ASCII only — the guaranteed content for this class of hardware
   * (see receiptLayout.ts's note on Tamil glyph support). */
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
  const widthBytes = Math.ceil(width / 8);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { bitmap: new Uint8Array(0), widthBytes: 0, height: 0 };

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);
  const { data } = ctx.getImageData(0, 0, width, height);

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

  const lines = buildReceiptLines(payload, options.paperWidthChars);
  for (const line of lines) {
    // The header/company lines are already included via buildReceiptLines;
    // skip the duplicate first line (display_name) since it's rendered
    // bold above.
    if (line.trim() === payload.company.display_name.trim()) continue;
    builder.text(line).newline();
  }

  builder.newline(3);
  builder.cutPartial();
  return builder.build();
}
