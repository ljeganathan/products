import type { BillPrintPayload, PrintPayloadItem } from "@/types/bill";
import { paiseToPlainAmount } from "@/utils/money";

export interface ReceiptItemRow {
  displayName: string;
  /** True when displayName has characters outside the single-byte ASCII
   * range (e.g. Tamil) — ESC/POS text mode (EscPosBuilder.text) can't
   * encode these, so the thermal builder rasters the name as an image
   * instead of printing these as plain text bytes. */
  isNonAscii: boolean;
  nameLines: string[];
  qtyRateLine: string;
  discountLine: string | null;
}

interface ReceiptLineOptions {
  /** Dot-matrix has no graphics mode at all, so it can never print a
   * rasterized Tamil name — force the English snapshot regardless of the
   * company's show_tamil_item_names setting. */
  forceEnglishNames?: boolean;
}

function resolveItemDisplayName(
  item: PrintPayloadItem,
  payload: BillPrintPayload,
  opts?: ReceiptLineOptions,
): string {
  const useTamil = !opts?.forceEnglishNames && payload.company.show_tamil_item_names;
  return useTamil && item.name_ta ? item.name_ta : item.name;
}

function isNonAsciiText(text: string): boolean {
  return Array.from(text).some((ch) => (ch.codePointAt(0) ?? 0) > 255);
}

export function buildReceiptHeaderLines(payload: BillPrintPayload, widthChars: number): string[] {
  const lines: string[] = [];
  const rule = "-".repeat(widthChars);

  lines.push(center(payload.company.display_name, widthChars));
  const addressLine = [payload.company.address, payload.company.pincode].filter(Boolean).join(" - ");
  if (addressLine) for (const l of wrap(addressLine, widthChars)) lines.push(center(l, widthChars));
  if (payload.company.gstin) lines.push(center(`GSTIN: ${payload.company.gstin}`, widthChars));
  if (payload.company.phone) lines.push(center(`Ph: ${payload.company.phone}`, widthChars));
  lines.push(rule);

  lines.push(twoCol(`Bill #${payload.bill_number}`, formatDate(payload.created_at), widthChars));
  lines.push(`Cashier: ${payload.cashier_name}`);
  if (payload.customer_name) lines.push(`Customer: ${payload.customer_name}`);
  if (payload.customer_phone) lines.push(`Phone: ${payload.customer_phone}`);
  lines.push(rule);

  return lines;
}

/** Structured per-item data — the thermal (ESC/POS) builder consumes this
 * directly so it can raster non-ASCII names instead of routing them through
 * plain text bytes; the preview/dot-matrix builders just flatten it. */
export function buildReceiptItemRows(
  payload: BillPrintPayload,
  widthChars: number,
  opts?: ReceiptLineOptions,
): ReceiptItemRow[] {
  return payload.items.map((item) => {
    const displayName = resolveItemDisplayName(item, payload, opts);
    const qtyRate = `${formatQty(item.qty)} x ${paiseToPlainAmount(item.unit_price_paise)}`;
    return {
      displayName,
      isNonAscii: isNonAsciiText(displayName),
      nameLines: wrap(displayName, widthChars),
      qtyRateLine: twoCol(qtyRate, paiseToPlainAmount(item.line_total_paise), widthChars),
      discountLine:
        item.discount_paise > 0
          ? twoCol("  Discount", `-${paiseToPlainAmount(item.discount_paise)}`, widthChars)
          : null,
    };
  });
}

export function buildReceiptTotalsFooterLines(payload: BillPrintPayload, widthChars: number): string[] {
  const lines: string[] = [];
  const rule = "-".repeat(widthChars);

  lines.push(rule);
  lines.push(twoCol("Subtotal", paiseToPlainAmount(payload.subtotal_paise), widthChars));
  if (payload.discount_paise > 0) {
    lines.push(twoCol("Discount", `-${paiseToPlainAmount(payload.discount_paise)}`, widthChars));
  }
  lines.push(twoCol("CGST", paiseToPlainAmount(payload.cgst_paise), widthChars));
  lines.push(twoCol("SGST", paiseToPlainAmount(payload.sgst_paise), widthChars));
  if (payload.round_off_paise !== 0) {
    const sign = payload.round_off_paise > 0 ? "+" : "";
    lines.push(twoCol("Round off", `${sign}${paiseToPlainAmount(payload.round_off_paise)}`, widthChars));
  }
  lines.push(rule);
  lines.push(twoCol("TOTAL", paiseToPlainAmount(payload.total_paise), widthChars));
  lines.push(twoCol("Payment", payload.payment_mode.toUpperCase(), widthChars));
  lines.push(rule);

  if (payload.company.invoice_footer_text) {
    for (const l of wrap(payload.company.invoice_footer_text, widthChars)) lines.push(center(l, widthChars));
  }
  lines.push(center("Thank you! Visit again.", widthChars));

  return lines;
}

/** Plain fixed-width text lines shared by the on-screen preview and the
 * dot-matrix builder — dot-matrix prints these almost verbatim (no
 * graphics), the preview renders them in an HTML <pre>. Item names honor
 * the Tamil-display setting here since both targets can render Tamil text
 * directly (a browser font for the preview); pass forceEnglishNames for
 * dot-matrix specifically, since that hardware has no graphics mode to
 * fall back on if a printer's code page can't show Tamil glyphs. */
export function buildReceiptLines(
  payload: BillPrintPayload,
  widthChars: number,
  opts?: ReceiptLineOptions,
): string[] {
  const lines: string[] = [...buildReceiptHeaderLines(payload, widthChars)];

  for (const row of buildReceiptItemRows(payload, widthChars, opts)) {
    lines.push(...row.nameLines);
    lines.push(row.qtyRateLine);
    if (row.discountLine) lines.push(row.discountLine);
  }

  lines.push(...buildReceiptTotalsFooterLines(payload, widthChars));
  return lines;
}

function formatQty(qty: number): string {
  return Number.isInteger(qty) ? String(qty) : qty.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function center(text: string, width: number): string {
  if (text.length >= width) return text.slice(0, width);
  const padding = Math.floor((width - text.length) / 2);
  return " ".repeat(padding) + text;
}

function twoCol(left: string, right: string, width: number): string {
  const gap = Math.max(1, width - left.length - right.length);
  if (left.length + right.length >= width) {
    return `${left.slice(0, width - right.length - 1)} ${right}`;
  }
  return left + " ".repeat(gap) + right;
}

function wrap(text: string, width: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if ((current + " " + word).trim().length > width) {
      if (current) lines.push(current);
      current = word;
    } else {
      current = (current + " " + word).trim();
    }
  }
  if (current) lines.push(current);
  return lines.length > 0 ? lines : [""];
}
