# Database Schema Reference — StoreMate TN

This is the authoritative schema reference. Phase 1 implements this as
SQLAlchemy models + Alembic migrations exactly. All monetary columns are
`BIGINT` storing paise (₹ × 100). All tables have `id UUID PK default
gen_random_uuid()`, `created_at`, `updated_at` unless noted.

## Deviations from this doc (Phase 1)

1. **`users.role` gains `product_owner`; `users.tenant_id` is nullable.**
   CLAUDE.md's role model (§0, §5) defines three roles, but this doc's
   `users` row only listed `admin|pos_user`. Since Phase 1's seed script and
   the platform's own auth model require a real `product_owner` account
   that isn't scoped to any tenant, `role` is `product_owner|admin|pos_user`
   and `tenant_id`/`store_id` are nullable (null = platform-level user).
2. **`discount_rules.value` is `BIGINT`, not left untyped.** The doc didn't
   specify a type for a column that serves double duty (a flat rupee amount
   *or* a percentage). To keep with the app-wide "no floats" convention
   (CLAUDE.md §3), it's stored as an integer: paise when `type=flat`,
   basis points when `type=percent` (10.50% → `1050`). Convert in the
   service layer.
3. **Quantity columns use `NUMERIC(12,3)`, not integer.** `quantity_on_hand`
   (stock), `reorder_level`/`reorder_qty` (items), `qty` (bill_items), and
   `change_qty` (stock_movements) are fractional-capable because
   `items.unit` includes weight/volume units (kg, g, l, ml) common in TN
   kirana retail (loose rice, oil by the litre, etc.). This doesn't
   conflict with the paise-integer rule, which applies to money only.

## Platform-level (no tenant_id — product_owner scope)

**plans**
`code (lite|pro|pro_max)`, `name`, `price_paise`, `max_users`, `max_stores`,
`max_printer_profiles`, `low_stock_alerts (bool)`, `saved_bill_days (int, -1=unlimited)`,
`features_json (jsonb)` — e.g. `{"low_stock_alerts": true, "multi_store":
false, "dashboard_range": true, "discount_rules_advanced": true,
"api_access": false}`, `is_active`

**tenants**
`name`, `owner_email`, `owner_phone`, `status (trial|active|suspended|cancelled)`,
`created_at`

**subscriptions**
`tenant_id FK`, `plan_id FK`, `status (active|past_due|cancelled)`,
`current_period_start`, `current_period_end`, `extra_users`, `extra_stores`,
`razorpay_subscription_id` (payment gateway reference, TBD provider)

**subscription_invoices**
`tenant_id FK`, `subscription_id FK`, `amount_paise`, `gst_paise`, `status`,
`invoice_number`, `issued_at`, `paid_at`

## Tenant-scoped (all include `tenant_id FK`, most include `store_id FK`)

**stores**
`tenant_id`, `name`, `address`, `gstin`, `phone`, `is_default`

**users**
`tenant_id (nullable = platform-level product_owner)`, `store_id (nullable
= all stores)`, `name`, `email`, `phone`, `password_hash`, `role
(product_owner|admin|pos_user)`, `is_active`, `language_pref (en|ta)`
— see "Deviations" above

**categories**
`tenant_id`, `name_en`, `name_ta`, `parent_category_id (nullable, for FMCG sub-categories)`,
`hsn_code (nullable)`

**items**
`tenant_id`, `store_id`, `category_id FK`, `name_en`, `name_ta`, `sku`,
`barcode (indexed, unique per tenant)`, `unit (pcs|kg|g|l|ml|box|pack)`,
`mrp_paise`, `selling_price_paise`, `cost_price_paise`, `tax_profile_id FK`,
`reorder_level`, `reorder_qty`, `is_active`
> FMCG-standard columns: `brand`, `pack_size` (e.g. "200g", "1L"),
> `hsn_code`, `batch_tracked (bool)` for future expiry/batch support.

**stock**
`tenant_id`, `store_id`, `item_id FK`, `batch_no (nullable)`,
`expiry_date (nullable)`, `quantity_on_hand`, `last_restocked_at`

**stock_movements** (audit trail — every +/- to stock)
`tenant_id`, `store_id`, `item_id FK`, `change_qty`, `reason
(purchase|sale|adjustment|return|damage)`, `reference_id (bill_id or PO id)`,
`created_by FK users`

**tax_profiles**
`tenant_id`, `name` (e.g. "GST 5%", "GST 18%", "Exempt"), `cgst_pct`,
`sgst_pct`, `igst_pct` (for future inter-state), `is_default`

**discount_rules** (Pro+)
`tenant_id`, `scope (item|category|bill)`, `target_id (nullable)`, `type
(flat|percent)`, `value`, `starts_at`, `ends_at`, `is_active`

**bills**
`tenant_id`, `store_id`, `bill_number (sequential per store)`, `cashier_id FK
users`, `customer_name (nullable)`, `customer_phone (nullable)`,
`subtotal_paise`, `discount_paise`, `cgst_paise`, `sgst_paise`,
`round_off_paise`, `total_paise`, `payment_mode (cash|card|upi|split)`,
`status (completed|held|cancelled)`, `printed_count`

**bill_items**
`bill_id FK`, `item_id FK`, `item_name_snapshot`, `qty`, `unit_price_paise`,
`discount_paise`, `tax_profile_snapshot_json`, `line_total_paise`

**printer_profiles**
`tenant_id`, `store_id`, `name`, `type (thermal_58mm|thermal_80mm|dot_matrix)`,
`connection (webusb|local_agent)`, `is_default`, `paper_width_chars`

**company_settings** (one row per store, effectively store master for
invoice header)
`tenant_id`, `store_id`, `legal_name`, `display_name`, `address`, `gstin`,
`fssai_no (nullable, common for FMCG/food retail)`, `phone`, `logo_url`,
`invoice_footer_text`

**notifications** (Pro/Pro Max low-stock etc.)
`tenant_id`, `store_id`, `type (low_stock|subscription|system)`,
`title`, `body`, `is_read`, `created_for_user_id (nullable = all admins)`

**audit_logs**
`tenant_id`, `user_id`, `action`, `entity`, `entity_id`, `metadata_json`,
`created_at`

## Indexes to include from day 1
- `items(tenant_id, barcode)` unique
- `items(tenant_id, store_id, name_en)` for fast search
- `bills(tenant_id, store_id, bill_number)` unique
- `stock(tenant_id, store_id, item_id)` unique
- `stock_movements(tenant_id, item_id, created_at)`
