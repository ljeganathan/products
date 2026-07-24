import type { DiscountType } from "@/types/bill";

export interface CalcLineInput {
  itemId: string;
  name: string;
  unitPricePaise: number;
  qty: number;
  cgstPct: number;
  sgstPct: number;
  discountType: DiscountType | null;
  discountValue: number | null;
}

export interface CalcLineResult {
  itemId: string;
  name: string;
  qty: number;
  unitPricePaise: number;
  grossPaise: number;
  discountPaise: number;
  cgstPaise: number;
  sgstPaise: number;
  lineTotalPaise: number;
}

export interface CalcTotals {
  lines: CalcLineResult[];
  subtotalPaise: number;
  discountPaise: number;
  cgstPaise: number;
  sgstPaise: number;
  roundOffPaise: number;
  totalPaise: number;
}

/** Mirrors Python's builtin round() (round-half-to-even) so this client
 * preview matches the server's authoritative totals engine
 * (backend/app/services/billing_service.py) bit-for-bit in the vast
 * majority of cases — both are IEEE754 double-precision arithmetic
 * evaluating the same formula. This is a *preview only*: POST /bills is
 * always what's actually charged and printed. */
function roundHalfEven(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  const EPS = 1e-9;
  if (diff < 0.5 - EPS) return floor;
  if (diff > 0.5 + EPS) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

function lineDiscount(grossPaise: number, type: DiscountType | null, value: number | null): number {
  if (!type || !value) return 0;
  if (type === "flat") return Math.min(value, grossPaise);
  return Math.min(roundHalfEven((grossPaise * value) / 10_000), grossPaise);
}

export function computeBillTotals(
  lines: CalcLineInput[],
  billDiscountType: DiscountType | null,
  billDiscountValue: number | null,
): CalcTotals {
  const grossPerLine = lines.map((l) => roundHalfEven(l.unitPricePaise * l.qty));
  const subtotalPaise = grossPerLine.reduce((a, b) => a + b, 0);

  const itemDiscountPerLine = lines.map((l, i) =>
    lineDiscount(grossPerLine[i], l.discountType, l.discountValue),
  );
  const netAfterItemDiscount = grossPerLine.map((g, i) => g - itemDiscountPerLine[i]);
  const netBeforeBillDiscount = netAfterItemDiscount.reduce((a, b) => a + b, 0);

  let billDiscountPaise = 0;
  if (billDiscountType && billDiscountValue && netBeforeBillDiscount > 0) {
    billDiscountPaise =
      billDiscountType === "flat"
        ? Math.min(billDiscountValue, netBeforeBillDiscount)
        : Math.min(
            roundHalfEven((netBeforeBillDiscount * billDiscountValue) / 10_000),
            netBeforeBillDiscount,
          );
  }

  const results: CalcLineResult[] = [];
  let totalCgst = 0;
  let totalSgst = 0;
  let allocated = 0;
  const lastIndex = lines.length - 1;

  lines.forEach((line, i) => {
    let share = 0;
    if (netBeforeBillDiscount > 0 && billDiscountPaise > 0) {
      share =
        i === lastIndex
          ? billDiscountPaise - allocated
          : roundHalfEven((billDiscountPaise * netAfterItemDiscount[i]) / netBeforeBillDiscount);
    }
    allocated += share;

    const taxable = Math.max(netAfterItemDiscount[i] - share, 0);
    const cgst = roundHalfEven((taxable * line.cgstPct) / 100);
    const sgst = roundHalfEven((taxable * line.sgstPct) / 100);
    totalCgst += cgst;
    totalSgst += sgst;

    results.push({
      itemId: line.itemId,
      name: line.name,
      qty: line.qty,
      unitPricePaise: line.unitPricePaise,
      grossPaise: grossPerLine[i],
      discountPaise: itemDiscountPerLine[i] + share,
      cgstPaise: cgst,
      sgstPaise: sgst,
      lineTotalPaise: taxable + cgst + sgst,
    });
  });

  const totalDiscountPaise = itemDiscountPerLine.reduce((a, b) => a + b, 0) + billDiscountPaise;
  const rawTotal = subtotalPaise - totalDiscountPaise + totalCgst + totalSgst;
  const roundedTotal = roundHalfEven(rawTotal / 100) * 100;

  return {
    lines: results,
    subtotalPaise,
    discountPaise: totalDiscountPaise,
    cgstPaise: totalCgst,
    sgstPaise: totalSgst,
    roundOffPaise: roundedTotal - rawTotal,
    totalPaise: roundedTotal,
  };
}
