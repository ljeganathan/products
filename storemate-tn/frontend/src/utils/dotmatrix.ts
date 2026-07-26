import type { BillPrintPayload } from "@/types/bill";
import { buildReceiptLines } from "@/utils/receiptLayout";

/** Dot-matrix continuous stationery has no ESC/POS graphics mode worth
 * relying on across the mixed fleet of legacy LPT/USB dot-matrix printers
 * still common in TN kirana back-offices — this is plain character-grid
 * text (CR/LF only), centered by padding with spaces since there's no
 * printer-side alignment command being used here. A form-feed (0x0C) ends
 * the page so continuous stationery advances to the next perforation.
 *
 * Item names always print in English here even when the Tamil-item-names
 * setting is on — unlike thermal (which rasters Tamil as an image, see
 * escpos.ts), dot-matrix has no graphics mode to fall back on, so Tamil
 * text bytes would just print as garbage on this hardware. */
export function buildDotMatrixReceipt(payload: BillPrintPayload, paperWidthChars: number): string {
  const lines = buildReceiptLines(payload, paperWidthChars, { forceEnglishNames: true });
  return lines.join("\r\n") + "\r\n\r\n\r\n\f";
}
