/** Validated categorical palette (dataviz skill's reference instance) for
 * dashboard/report charts with dynamic, non-brand-fixed categories
 * (category/cashier/payment-mode breakdowns). Fixed order — never cycled
 * per-render — so a filtered-down series always keeps its color.
 * Passes `validate_palette.js` in light mode (this app has no dark mode). */
export const CATEGORICAL_COLORS = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
] as const;

/** Single-hue sequential ramp (light -> dark blue) for one-series magnitude
 * encodings — the sales trend line/area. */
export const SEQUENTIAL_BLUE = "#2a78d6";
export const SEQUENTIAL_BLUE_FILL = "#2a78d61a"; // ~10% opacity wash, per marks-and-anatomy.md

/** Plan tiers are a fixed, brand-meaningful category already color-coded
 * everywhere else in the console (components/ui/Badge.tsx) — reused here
 * rather than the generic categorical palette so a plan's color means the
 * same thing on every screen. */
export const PLAN_TIER_COLORS: Record<string, string> = {
  lite: "#64748b", // slate-500, matches Badge's lite variant
  pro: "#0d9488", // teal-600, matches Badge's pro variant
  pro_max: "#ea580c", // brand-600, matches Badge's pro_max variant
};

export const CHART_INK = {
  primary: "#0b0b0b",
  secondary: "#52514e",
  muted: "#898781",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  surface: "#fcfcfb",
};
