import { describe, expect, it } from "vitest";

import { computeBillTotals, type CalcLineInput } from "@/utils/billingCalc";

function line(overrides: Partial<CalcLineInput> = {}): CalcLineInput {
  return {
    itemId: "item-1",
    name: "Test Item",
    unitPricePaise: 10_000,
    qty: 1,
    cgstPct: 9,
    sgstPct: 9,
    discountType: null,
    discountValue: null,
    ...overrides,
  };
}

describe("computeBillTotals", () => {
  it("computes a single line with no discount and no tax", () => {
    const result = computeBillTotals(
      [line({ unitPricePaise: 10_000, qty: 2, cgstPct: 0, sgstPct: 0 })],
      null,
      null,
    );
    expect(result.subtotalPaise).toBe(20_000);
    expect(result.cgstPaise).toBe(0);
    expect(result.sgstPaise).toBe(0);
    expect(result.discountPaise).toBe(0);
    expect(result.totalPaise).toBe(20_000);
  });

  it("applies CGST+SGST per line at the item's own slab", () => {
    // 18% GST FMCG slab: 100.00 -> 9.00 CGST + 9.00 SGST = 118.00
    const result = computeBillTotals(
      [line({ unitPricePaise: 10_000, qty: 1, cgstPct: 9, sgstPct: 9 })],
      null,
      null,
    );
    expect(result.cgstPaise).toBe(900);
    expect(result.sgstPaise).toBe(900);
    expect(result.totalPaise).toBe(11_800);
  });

  it("supports a mixed-rate cart — each line keeps its own GST slab", () => {
    const result = computeBillTotals(
      [
        line({ itemId: "a", unitPricePaise: 10_000, qty: 1, cgstPct: 9, sgstPct: 9 }), // 18%
        line({ itemId: "b", unitPricePaise: 10_000, qty: 1, cgstPct: 2.5, sgstPct: 2.5 }), // 5%
      ],
      null,
      null,
    );
    // line a: 900+900=1800 tax; line b: 250+250=500 tax
    expect(result.cgstPaise).toBe(1_150);
    expect(result.sgstPaise).toBe(1_150);
    expect(result.subtotalPaise).toBe(20_000);
  });

  it("applies a flat item-level discount before tax", () => {
    const result = computeBillTotals(
      [
        line({
          unitPricePaise: 10_000,
          qty: 1,
          cgstPct: 9,
          sgstPct: 9,
          discountType: "flat",
          discountValue: 1_000, // ₹10 off
        }),
      ],
      null,
      null,
    );
    // taxable = 10000 - 1000 = 9000; cgst=sgst=810; raw total 10620 paise
    // (₹106.20) rounds to the nearest rupee, ₹106.00 = 10600 paise.
    expect(result.discountPaise).toBe(1_000);
    expect(result.cgstPaise).toBe(810);
    expect(result.sgstPaise).toBe(810);
    expect(result.totalPaise).toBe(10_600);
    expect(result.roundOffPaise).toBe(-20);
  });

  it("applies a percent item-level discount using basis points", () => {
    const result = computeBillTotals(
      [
        line({
          unitPricePaise: 10_000,
          qty: 1,
          cgstPct: 0,
          sgstPct: 0,
          discountType: "percent",
          discountValue: 1_000, // 10.00%
        }),
      ],
      null,
      null,
    );
    expect(result.discountPaise).toBe(1_000);
    expect(result.totalPaise).toBe(9_000);
  });

  it("clamps a discount that would exceed the line's gross amount", () => {
    const result = computeBillTotals(
      [
        line({
          unitPricePaise: 5_000,
          qty: 1,
          cgstPct: 0,
          sgstPct: 0,
          discountType: "flat",
          discountValue: 50_000, // way more than the line total
        }),
      ],
      null,
      null,
    );
    expect(result.discountPaise).toBe(5_000);
    expect(result.totalPaise).toBe(0);
  });

  it("prorates a bill-level discount across lines by post-item-discount share", () => {
    const result = computeBillTotals(
      [
        line({ itemId: "a", unitPricePaise: 30_000, qty: 1, cgstPct: 0, sgstPct: 0 }),
        line({ itemId: "b", unitPricePaise: 10_000, qty: 1, cgstPct: 0, sgstPct: 0 }),
      ],
      "flat",
      4_000, // ₹40 off the ₹400 bill, split 3:1 by share
    );
    expect(result.discountPaise).toBe(4_000);
    // line a share: round(4000 * 30000/40000) = 3000; line b absorbs the remainder = 1000
    expect(result.lines[0].discountPaise).toBe(3_000);
    expect(result.lines[1].discountPaise).toBe(1_000);
    expect(result.totalPaise).toBe(36_000);
  });

  it("applies a bill-level percent discount", () => {
    const result = computeBillTotals(
      [line({ unitPricePaise: 20_000, qty: 1, cgstPct: 0, sgstPct: 0 })],
      "percent",
      500, // 5.00%
    );
    expect(result.discountPaise).toBe(1_000);
    expect(result.totalPaise).toBe(19_000);
  });

  it("rounds the grand total to the nearest rupee and reports the remainder as round-off", () => {
    // 9% + 9% on 10333 paise -> raw total isn't a clean rupee amount
    const result = computeBillTotals(
      [line({ unitPricePaise: 10_333, qty: 1, cgstPct: 9, sgstPct: 9 })],
      null,
      null,
    );
    expect(result.totalPaise % 100).toBe(0);
    const rawTotal = result.subtotalPaise - result.discountPaise + result.cgstPaise + result.sgstPaise;
    expect(result.totalPaise - rawTotal).toBe(result.roundOffPaise);
  });

  it("handles an empty bill-level discount gracefully when net is zero", () => {
    const result = computeBillTotals(
      [
        line({
          unitPricePaise: 5_000,
          qty: 1,
          cgstPct: 0,
          sgstPct: 0,
          discountType: "flat",
          discountValue: 5_000, // fully discounted line
        }),
      ],
      "percent",
      1_000,
    );
    expect(result.totalPaise).toBe(0);
    expect(result.discountPaise).toBe(5_000);
  });
});
