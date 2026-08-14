import type { BillPrintPayload, CompanySettings } from "@/types/bill";

/** Synthetic payload for the Settings "Test Print" button — reuses the
 * exact same print pipeline (escpos.ts / dotmatrix.ts / printDispatch.ts) a
 * real sale would, but with fake line items, so a store can verify a
 * printer profile and their company header/logo without ringing up a sale.
 * `payment_mode` is "upi" (rather than "cash") specifically so this test
 * print also exercises the UPI QR code — printDispatch.ts only renders it
 * for `payment_mode: "upi"` bills, and without that here a store could
 * never preview/verify the QR print without ringing up a real UPI sale. */
export function buildSampleReceiptPayload(company: CompanySettings): BillPrintPayload {
  return {
    bill_number: 0,
    created_at: new Date().toISOString(),
    cashier_name: "Test Print",
    customer_name: null,
    customer_phone: null,
    company,
    items: [
      {
        name: "Sample Item A",
        name_ta: "மாதிரி பொருள் A",
        qty: 2,
        unit_price_paise: 5000,
        discount_paise: 0,
        line_total_paise: 11800,
      },
      {
        name: "Sample Item B",
        name_ta: "மாதிரி பொருள் B",
        qty: 1,
        unit_price_paise: 2500,
        discount_paise: 250,
        line_total_paise: 2655,
      },
    ],
    subtotal_paise: 12500,
    discount_paise: 250,
    cgst_paise: 1102,
    sgst_paise: 1102,
    round_off_paise: -49,
    total_paise: 14455,
    payment_mode: "upi",
  };
}
