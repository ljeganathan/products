import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Indian lakh/crore digit grouping, ₹ with no space, paise only when non-zero
// (CLAUDE.md §9) — e.g. ₹1,25,000 or ₹120.50, never ₹120.00.
export function formatINR(amount: number): string {
  const hasPaise = Math.round(amount * 100) % 100 !== 0;
  const formatted = new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: hasPaise ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(amount);
  return `₹${formatted}`;
}
