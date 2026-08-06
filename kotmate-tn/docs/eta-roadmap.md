# KOTMate TN — Phase-wise ETA

Estimates assume one focused full-stack developer (you + Claude Code pair-programming), working iteratively phase by phase, ~4-6 focused hours/day. Adjust down if working part-time evenings only (roughly 2x the numbers below).

| Phase | Scope | ETA |
|---|---|---|
| 00 | Bootstrap (repo, Docker, base configs) | 0.5 day |
| 01 | Database schema + migrations (incl. sections, item_section_prices, user_id login) | 2 days |
| 02 | Auth + RBAC (user_id login, no email) | 1.5 days |
| 03 | Product Owner console (tenants/Company Master, plans + location caps, maintenance) | 2 days |
| 04 | User management panel (incl. cashier incentive rate) | 1.5 days |
| 05 | Item + Category master (Tamil, images, per-section price overrides) | 2.5 days |
| 06 | Waiter + Seating Sections + Table master | 1 day |
| 07 | POS core screen (desktop/tablet/mobile, keyboard+touch, section-aware pricing, cashier incentive) | 5-6 days |
| 08 | KOT + printer integration + Kitchen Display | 3 days |
| 09 | Billing: tax, discount, split payment, QR, print (table/section on bill) | 3.5 days |
| 10 | Settings + Hotel Master + Company Master (multi-location, all tiers) | 2 days |
| 11 | Reports + Dashboard (incl. waiter/cashier sales + incentive reports) | 3 days |
| 12 | Import/export, hardening, deployment | 2.5 days |
| **Total** | | **~30-31 working days (~6 weeks)** |

**Suggested milestones for demo-ability:**
- End of Phase 07: internal demo — full POS billing flow (no printing/tax yet) usable on desktop + mobile.
- End of Phase 09: first paid-pilot-ready build (billing complete, KOT working).
- End of Phase 11: full Lite/Pro/Pro Max feature-complete build, ready for pilot restaurant onboarding.
- End of Phase 12: production launch on Hostinger.

Risk buffers: printer hardware integration (Phase 08) and Tamil font/print rendering (Phase 09) are the two most likely to run over — budget 20% contingency on those two phases specifically.
