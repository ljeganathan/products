# Subscription Tiers — StoreMate TN

Pricing assumes a single-store Tamil Nadu FMCG retail shop as the baseline
buyer, billed monthly, INR, exclusive of GST on the SaaS fee itself (18%
GST applies additionally on the subscription invoice, standard for SaaS in
India). Annual billing suggested at ~2 months free (≈17% discount) to
improve retention/cashflow — figures below are monthly list price.

## Lite — ₹799/month (₹7,999/year)
Best for a single small kirana store just moving off manual/register billing.
- 1 store, up to 2 users (1 admin + 1 pos_user)
- POS billing: barcode + keyboard entry, fast item search
- Item & category master (Tamil + English)
- Stock entry & availability view (manual reorder — no auto alerts)
- Manual bill-level discount
- Configurable tax (single tax profile)
- 1 printer profile (thermal **or** dot-matrix)
- Saved bill search — last 7 days
- **Dashboard: today-only snapshot** — today's sales total, bill count, top 5 items, current stock alerts count (no trend charts)
- Basic daily sales report (on-screen only)
- Email support

## Pro — ₹1,999/month (₹19,999/year)
Best for a growing single-store or two-counter supermarket.
Everything in Lite, plus:
- Up to 5 users
- **Low-stock notifications** (threshold per item, in-app + email)
- Item-level and category-level discount rules
- Up to 3 printer profiles (mix thermal + dot-matrix, per counter)
- Saved bill search — last 90 days
- **Dashboard: date-range view** — sales trend chart, category & cashier breakdown, low-stock widget, payment-mode split, hourly sales heatmap
- Advanced reports: date-range sales, GST summary (CGST/SGST), CSV export
- Priority (chat) support

## Pro Max — ₹3,999/month (₹39,999/year)
Best for multi-counter supermarkets or small chains (2+ store locations).
Everything in Pro, plus:
- Unlimited users
- Multi-store under one tenant (consolidated + per-store reporting)
- Unlimited printer profiles
- Unlimited saved bill history
- Scheduled/automatic promotions engine
- **Dashboard: multi-store consolidated + per-store drill-down**, customizable/reorderable widgets, target-vs-actual tracking, export dashboard as PDF for owner review
- Scheduled email reports (daily/weekly owner summary)
- API access for integrations (accounting software, WhatsApp billing, etc.)
- Priority phone + chat support, onboarding assistance

## Add-ons (all plans)
- Extra user beyond plan limit: ₹99/user/month (Lite/Pro only; Pro Max unlimited)
- Extra store beyond plan default: ₹999/store/month (Pro Max only)
- SMS bill notification to customer: ₹0.20/SMS, billed as usage

## Notes for the product-owner console
- Plan changes take effect immediately; downgrades are blocked if current
  usage (users/stores/printer profiles) exceeds the target plan's limits —
  the UI must show what needs to be reduced first.
- All limits above are enforced server-side in
  `backend/app/middleware/plan_limits.py`, sourced from a `plans` table so
  prices/limits can be changed by the product owner without a code
  deployment.
