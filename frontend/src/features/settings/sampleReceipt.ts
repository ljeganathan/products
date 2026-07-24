import type { BillPrintPayload, CompanySettings } from "@/types/bill";

/** Synthetic payload for the Settings "Test Print" button — reuses the
 * exact same print pipeline (escpos.ts / dotmatrix.ts / printDispatch.ts) a
 * real sale would, but with fake line items, so a store can verify a
 * printer profile and their company header/logo without ringing up a sale. */
export function buildSampleReceiptPayload(company: CompanySettings): BillPrintPayload {
  return {
    bill_number: 0,
    created_at: new Date().toISOString(),
    cashier_name: "Test Print",
    customer_name: null,
    customer_phone: null,
    company,
    items: [
      { name: "Sample Item A", qty: 2, unit_price_paise: 5000, discount_paise: 0, line_total_paise: 11800 },
      { name: "Sample Item B", qty: 1, unit_price_paise: 2500, discount_paise: 250, line_total_paise: 2655 },
    ],
    subtotal_paise: 12500,
    discount_paise: 250,
    cgst_paise: 1102,
    sgst_paise: 1102,
    round_off_paise: -49,
    total_paise: 14455,
    payment_mode: "cash",
  };
}
