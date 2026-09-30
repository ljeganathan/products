# Online payments (Razorpay) — QR self-order

Customers who order from a table/takeaway QR can pay on their phone. Google Pay and PhonePe
open directly; everything else (other UPI apps, UPI ID, card, netbanking) goes through
Razorpay's own checkout. Pro Max only (same gate as QR self-order).

## How a hotel turns it on (Model A: the hotel's own Razorpay account)
1. Hotel creates a Razorpay account and completes KYC at razorpay.com.
2. Razorpay dashboard → Account & Settings → API keys → generate a key (test keys start
   `rzp_test_`, live keys `rzp_live_`).
3. KOTMate → Settings → Preferences → **Online payments (Razorpay)**: paste Key ID and Key
   secret, press **Save keys**, then **Test connection**, then switch on **Accept online payments**.
4. Optional but recommended in production: Razorpay dashboard → Webhooks → add the URL shown in
   that card, choose `payment.captured`, `payment.failed`, `order.paid`, and paste the webhook
   secret into KOTMate.

Money goes straight to the hotel's bank account; KOTMate never holds it. Razorpay's fee
(currently ~2% + GST) is paid by the hotel.

## How it works
- Guest taps Pay → `POST /guest/payments/create`. The **server** works out the amount from the
  order and creates a Razorpay order with the hotel's own keys. The client never sends an amount.
- The guest page opens Razorpay (custom checkout `createPayment` for Google Pay/PhonePe, standard
  checkout for the rest), then polls `GET /guest/payments/status`.
- Each status call (and the webhook, if configured) re-reads the order's payments from Razorpay.
  A payment counts only if it is `captured` (or `authorized`, which we capture) **for exactly the
  order amount**. So it works without any public webhook, e.g. on a local machine.
- Once paid: the guest session moves to the existing "guest paid" state (staff see it on the KOT
  Tickets list and by live toast), the cart is locked, and the staff Finalize Bill screen shows
  "Paid online ₹X · pay_…" and preselects UPI. The Razorpay payment id is saved on the bill's
  payment line (`payments.reference`) for reconciliation.

## Where things live
| Piece | File |
|---|---|
| Gateway client + credential resolution (only place that talks to Razorpay) | `backend/app/services/payment_gateway.py` |
| Attempt lifecycle, settings, guest flow, webhook handling | `backend/app/services/online_payment_service.py` |
| Tables | `tenant_payment_gateways`, `payment_attempts`, `payments.reference` (migration `e5b2c7d91a34`) |
| Secret encryption | `backend/app/core/secrets.py` (`PAYMENT_SECRETS_KEY`) |
| Owner settings screen | `frontend/src/modules/admin/OnlinePaymentsSettings.tsx` |
| Guest pay card | `frontend/src/modules/guest/OnlinePayCard.tsx` |

## Moving to Razorpay's Partner program (Model B) later
`tenant_payment_gateways.auth_mode` is `api_keys` today. For Partner sub-merchants, add a
`partner_oauth` branch in `payment_gateway.build_gateway` (bearer access token, refreshed before
its 90-day expiry; `account_ref` holds the sub-merchant account id) and an onboarding screen that
creates/updates the row. The guest flow, webhook, staff screens and reports do not change.

## Production notes
- Set `PUBLIC_BASE_URL` (webhook address shown to owners) and `PAYMENT_SECRETS_KEY` in `.env`.
- Razorpay checkout scripts load from `checkout.razorpay.com`; the app sets no CSP header, so
  nothing to allow. If a CSP is ever added, allow that host (script, frame) and `api.razorpay.com`.
- Test mode moves no real money. Whether the real GPay/PhonePe app opens in test mode is not
  documented by Razorpay; verify the app hand-off in live mode with a ₹1 payment.
