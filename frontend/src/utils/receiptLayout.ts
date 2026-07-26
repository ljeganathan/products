import type { BillPrintPayload } from "@/types/bill";
import { paiseToPlainAmount } from "@/utils/money";

/** Plain fixed-width text lines shared by both the ESC/POS (thermal) and
 * dot-matrix builders — dot-matrix prints these lines almost verbatim
 * (no graphics), thermal wraps them with ESC/POS formatting commands.
 *
 * Note: item names print in English (name_en) only. Thermal/dot-matrix
 * printers in this class have no Tamil glyph support without
 * printer-specific firmware — there is no reliable byte encoding for Tamil
 * script on this hardware class, so this is a real hardware limitation,
 * not an oversight. */
export function buildReceiptLines(payload: BillPrintPayload, widthChars: number): string[] {
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

  for (const item of payload.items) {
    for (const l of wrap(item.name, widthChars)) lines.push(l);
    const qtyRate = `${formatQty(item.qty)} x ${paiseToPlainAmount(item.unit_price_paise)}`;
    lines.push(twoCol(qtyRate, paiseToPlainAmount(item.line_total_paise), widthChars));
    if (item.discount_paise > 0) {
      lines.push(twoCol("  Discount", `-${paiseToPlainAmount(item.discount_paise)}`, widthChars));
    }
  }
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
