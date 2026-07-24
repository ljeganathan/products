import type { VariantProps } from "class-variance-authority";

import type { badgeVariants } from "@/components/ui/Badge";

/** Maps a stock quantity/reorder-level pair to the right semantic Badge
 * variant, so stock-status color coding stays consistent everywhere it's
 * used (stock list, POS search results, low-stock widgets). */
export function stockStatusVariant(
  quantityOnHand: number,
  reorderLevel: number,
): VariantProps<typeof badgeVariants>["variant"] {
  if (quantityOnHand <= 0) return "danger";
  if (quantityOnHand <= reorderLevel) return "warning";
  return "success";
}
