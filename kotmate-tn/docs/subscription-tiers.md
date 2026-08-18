# KOTMate TN — Subscription Tiers & Pricing

See `CLAUDE.md` §6 for the original planning-stage feature matrix. Pricing summary:

| Tier | Monthly (INR) | Yearly (INR) | Users | Locations | Images | KOT Screen + Print | Section pricing |
|---|---------------|--------------|---|---|---|---|---|
| Lite | ₹499          | ₹4,999       | 2 | 1 | ❌ | ❌ (bill directly) | ❌ |
| Pro | ₹799           | ₹7,999       | 6 | up to 2 | ✅ | ❌ (bill directly) | ✅ |
| Pro Max | ₹1,499        | ₹14,999      | Unlimited | up to 5 | ✅ | ✅ | ✅ |

**Add-ons:** extra POS seat ₹199/mo · extra hotel location beyond plan cap (Pro/Pro Max only) ₹999/location/mo · onboarding/data migration ₹2,999 one-time · SMS/WhatsApp bill notify ₹0.35/msg (future).

Login is by `user_id` (not email) for every role, including Product Owner. Every tier now includes a Company Master for adding hotel locations up to its cap, a Seating Sections master (AC/Non-AC/Rooftop/Family/Takeaway/Online Delivery) with per-table tagging, and waiter + cashier incentive tracking. Only per-section item price overrides are Pro+.

**Notes for pricing validation:** Benchmark against Petpooja, Posist, and local TN POS vendors before locking final numbers — small single-counter shops are price-sensitive (~₹500–₹1,500/mo band is common), while multi-branch hotel chains tolerate ₹5,000+/location if reporting/reconciliation is strong. Consider a 14-day free trial on Pro to drive upgrade conversion from Lite.

---

## Full feature availability (as actually shipped in the current build)

Cross-checked against the running application, not just the original plan — includes everything verified working end-to-end (incl. physical printing, tested against real thermal hardware).

### Core billing & KOT
| Feature | Lite | Pro | Pro Max |
|---|:---:|:---:|:---:|
| POS billing screen (desktop, tablet, mobile) | ✅ | ✅ | ✅ |
| KOT ticket screen + KOT User login (`kitchen` role) | ❌ (production feedback round 2 — was on-screen-only ✅ before; bills go straight through instead) | ❌ | ✅ |
| KOT ticket — physical printer | ❌ | ❌ | ✅ |
| Kitchen Display System (live ticket queue) | ❌ | ❌ | ✅ |
| POS Operator login (`pos_operator` — POS-screen-only staff account, no Reports/Dashboard access) | ❌ | ❌ | ✅ |
| Hold / recall bill | ✅ | ✅ | ✅ |
| Multi-payment split (Cash + UPI + Card, any mix) | ✅ | ✅ | ✅ |
| Table & seating-section management with live floor status | ✅ | ✅ | ✅ |
| Seat/customer splitting at one table (multiple concurrent bills) | ✅ | ✅ | ✅ |
| Multi-location switcher (POS + Dashboard) | ✅ (1 location) | ✅ (up to 2) | ✅ (up to 5) |
| Item-code quick entry + barcode-style fast billing | ✅ | ✅ | ✅ |
| Bilingual English + Tamil item names on screen | ✅ | ✅ | ✅ |

### Physical printing
| Feature | Lite | Pro | Pro Max |
|---|:---:|:---:|:---:|
| Bill printer (thermal 58/80mm, auto width-adjusting layout) | ✅ | ✅ | ✅ |
| Works from USB (desktop, laptop, or Android phone/tablet — no drivers) | ✅ | ✅ | ✅ |
| Works via a lightweight local print-agent (shared network/Windows printer) | ✅ | ✅ | ✅ |
| Tamil item names print correctly on paper (not just screen) | ✅ | ✅ | ✅ |
| Hotel logo on printed bill (auto-scaled to paper width) | ✅ | ✅ | ✅ |
| Bold, large-print Grand Total and KOT ticket number | ✅ | ✅ | ✅ |
| Custom "Thank You" / promotional footer message on every bill | ✅ | ✅ | ✅ |
| UPI QR code on bill — shown only when the customer actually pays via UPI | ✅ | ✅ | ✅ |
| Table number + seating section printed on every bill and ticket | ✅ | ✅ | ✅ |
| Waiter name + bill date/time on printed bill | ✅ | ✅ | ✅ |

### Menu, tax & discounts
| Feature | Lite | Pro | Pro Max |
|---|:---:|:---:|:---:|
| Item master with Tamil name | ✅ | ✅ | ✅ |
| Item photo upload | ❌ | ✅ | ✅ |
| Category master with icons | ✅ | ✅ | ✅ |
| Item import/export (CSV, Tamil-safe encoding) | ❌ | ✅ | ✅ |
| Per-seating-section price override (e.g. AC vs Non-AC pricing) | ❌ | ✅ | ✅ |
| Top-selling quick-tiles (auto-ranked, image-backed) | text-only | ✅ | ✅ |
| GST — CGST/SGST | single rate | multi-rate | multi-rate + per-item override |
| Discount rules — auto-applied, no cashier math | flat % only | flat % + item-level | flat + item-level + coupon codes |
| Low-stock / out-of-stock badges on POS & KOT | ✅ | ✅ | ✅ |
| Full stock audit ledger + tenant on/off switch | ❌ | ✅ | ✅ |
| Stock Management tab (bulk category-grouped view + "+ Add Stock" increment popup) | ❌ | ❌ (lives on the now Pro-Max-only KOT screen) | ✅ |

### Staff & operations
| Feature | Lite | Pro | Pro Max |
|---|:---:|:---:|:---:|
| Waiter master | ✅ | ✅ | ✅ |
| Cashier, waiter & POS Operator incentive-rate tracking | ✅ (cashier/waiter) | ✅ (cashier/waiter) | ✅ (cashier/waiter/POS Operator) |
| User seats (Admin + POS + Waiter logins; KOT/POS Operator logins are Pro Max only, see above) | up to 2 | up to 6 | Unlimited |
| Bill History search (by number, date, table, waiter, cashier) | ✅ | ✅ | ✅ |
| Audit log for discounts & price overrides | ✅ | ✅ | ✅ |
| Daily Z-report / shift close | ✅ | ✅ | ✅ |

### Reports & dashboard
| Feature | Lite | Pro | Pro Max |
|---|:---:|:---:|:---:|
| Dashboard KPIs (today's sales, bill count, avg. bill) | ✅ (Cashier login sees Top Selling + Low Stock only, no sales figures) | ✅ (Cashier login sees Top Selling + Low Stock only, no sales figures) | ✅ (Cashier login sees Top Selling + Low Stock only, no sales figures) |
| Charts & trends | ❌ | ✅ | ✅ |
| Sales / item / category / tax / waiter / cashier / POS Operator reports | view only (no POS Operator report — role is Pro Max only) | + CSV export (no POS Operator report — role is Pro Max only) | + PDF & Excel export, incl. POS Operator-wise sales/incentive |
| Waiter, cashier & POS Operator incentive payout worksheets | ✅ (waiter/cashier) | ✅ (waiter/cashier) | ✅ (waiter/cashier/POS Operator) |
| Report printing (any report to a dedicated printer, plain text) | ❌ | ❌ | ✅ (tenant on/off switch in Settings → Preferences) |
| Multi-location comparison view | ❌ | ❌ | ✅ — `tenant_admin` only, hidden from Cashier |
| Priority support | ❌ | ❌ | ✅ |

### Mobile & tablet
Every tier gets the same POS app on desktop, tablet, and phone — no separate mobile app or extra license. A phone or tablet can run the full counter (billing + printing) or a waiter's order-taking device on the floor, cashier's choice.
