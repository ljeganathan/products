/** Money is always stored/transmitted as integer paise (CLAUDE.md §3);
 * formatting to ₹ happens only at the UI layer, here. */
export function formatPaise(paise: number): string {
  return (paise / 100).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });
}

/** Plain "123.45" (no currency symbol/grouping) for fixed-width print layouts. */
export function paiseToPlainAmount(paise: number): string {
  return (paise / 100).toFixed(2);
}

/** Compact Indian-numbering ₹ for chart axes/stat tiles: "₹1,284", "₹12.9K",
 * "₹4.20L", "₹1.50Cr" — matches how a TN retail owner actually reads large
 * rupee amounts, rather than the generic K/M/B convention. */
export function formatPaiseCompact(paise: number): string {
  const rupees = paise / 100;
  const sign = rupees < 0 ? "-" : "";
  const abs = Math.abs(rupees);

  if (abs >= 1_00_00_000) return `${sign}₹${(abs / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `${sign}₹${(abs / 1_00_000).toFixed(2)}L`;
  if (abs >= 1_000) return `${sign}₹${(abs / 1_000).toFixed(1)}K`;
  return `${sign}₹${Math.round(abs).toLocaleString("en-IN")}`;
}
