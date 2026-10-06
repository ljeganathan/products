# Online payments (Razorpay or Cashfree) — QR self-order

Customers who order from a table/takeaway QR can pay on their phone. Razorpay or Cashfree
takes the payment, and the money goes straight to the hotel's own bank account. Pro Max only
(same gate as QR self-order).

The owner picks **one** provider at a time in KOTMate → Settings → Preferences → **Online
payments**. Turning one on switches the other off. Payments already in flight keep settling
through the provider they were created with, so a switch never strands a customer mid-payment.

## How a hotel turns it on (Model A: the hotel's own account)

### Razorpay
1. Hotel creates a Razorpay account and completes KYC at razorpay.com.
2. Razorpay dashboard → Account & Settings → API keys → generate a key (test keys start
   `rzp_test_`, live keys `rzp_live_`).
3. KOTMate → Settings → Preferences → **Online payments**, choose **Razorpay**, paste Key ID and
   Key secret, press **Save keys**, then **Test connection**, then switch on **Accept online
   payments**.
4. Optional but recommended in production: Razorpay dashboard → Webhooks → add the URL shown in
   that card, choose `payment.captured`, `payment.failed`, `order.paid`, and paste the webhook
   secret into KOTMate.

### Cashfree
1. Hotel creates a Cashfree account and completes KYC at cashfree.com.
2. Cashfree dashboard → Developers → API keys. Copy the **Client ID** and **Client secret**.
   Use the **Sandbox** keys to test first, and the **Production** keys once KYC is approved.
3. KOTMate → Settings → Preferences → **Online payments**, choose **Cashfree**, paste the Client
   ID and Client secret, pick **Sandbox** or **Production** to match those keys, press **Save
   keys**, then **Test connection**, then switch on **Accept online payments**. KOTMate refuses to
   switch Cashfree on until an environment is chosen.
4. Optional but recommended: Cashfree dashboard → Developers → Webhooks → add the URL shown in
   that card, and subscribe to the payment success and payment failed events.

Money goes straight to the hotel's bank account; KOTMate never holds it. Each provider's fee is
paid by the hotel.

## How it works
- Guest taps Pay → `POST /guest/payments/create`. The **server** works out the amount from the
  order and creates the order with the hotel's own keys. The client never sends an amount.
- Razorpay: the guest page opens Razorpay's checkout (custom checkout `createPayment` for Google
  Pay / PhonePe, standard checkout for the rest).
- Cashfree: the guest page opens Cashfree's checkout with the `payment_session_id` from the
  server. Cashfree's checkout lists every UPI app, card and netbanking on one screen, so there are
  no separate Google Pay / PhonePe buttons.
- In both cases the guest page then polls `GET /guest/payments/status`.
- Each status call (and the webhook, if configured) re-reads the order's payments from the
  gateway. A payment counts only if it is captured (Razorpay: `captured` or `authorized`, which we
  capture) **for exactly the order amount**. So it works without any public webhook, e.g. on a
  local machine.
- Once paid: the guest session moves to the existing "guest paid" state (staff see it on the KOT
  Tickets list and by live toast), the cart is locked, and the staff Finalize Bill screen shows
  "Paid online ₹X" and preselects **Online**. The gateway payment id is saved on the bill's payment
  line (`payments.reference`) for reconciliation.

## Bill payment method "Online"
- Billing offers **UPI, Online, Cash, Card**. **Online** is the verified online payment from a QR
  order. It is also used for a counter payment taken through an online or app channel.
- Paid QR orders are recorded as `online`, not `upi`. Old `upi` bills are not changed.
- Reports show an **Online** line in the payment breakdown. The printed Sales Summary and Z-Report
  only show the Online line when the period has online payments, so reports for hotels that don't
  use it look the same as before.
- The UPI QR code on a printed bill still appears only for real UPI payments.

## Where things live
| Piece | File |
|---|---|
| Gateway clients (Razorpay, Cashfree) + credential resolution (only place that talks to either) | `backend/app/services/payment_gateway.py` |
| Attempt lifecycle, settings, guest flow | `backend/app/services/online_payment_service.py` |
| Webhooks: `/webhooks/razorpay/{tenant}` and `/webhooks/cashfree/{tenant}` | `backend/app/api/v1/webhooks.py` |
| Tables | `tenant_payment_gateways` (one row per tenant per provider, at most one enabled), `payment_attempts`, `payments.reference` |
| Migration | `backend/alembic/versions/c4e8a2d6b1f7_cashfree_and_online_payment_method.py` |
| Secret encryption | `backend/app/core/secrets.py` (`PAYMENT_SECRETS_KEY`) |
| Owner settings screen | `frontend/src/modules/admin/OnlinePaymentsSettings.tsx` |
| Guest pay card | `frontend/src/modules/guest/OnlinePayCard.tsx` |

## Production notes
- Set `PUBLIC_BASE_URL` (webhook address shown to owners) and `PAYMENT_SECRETS_KEY` in `.env`.
- The migration only adds a column and widens allowed values. It doesn't change existing rows.
  Existing Razorpay setups keep working, including the webhook URL already saved in the hotel's
  Razorpay dashboard.
- Razorpay checkout scripts load from `checkout.razorpay.com`. Cashfree's checkout script loads
  from `sdk.cashfree.com`. The app sets no CSP header, so nothing to allow. If a CSP is ever added,
  allow those hosts, and `api.razorpay.com` / `sandbox.cashfree.com` / `api.cashfree.com`.
- Test mode moves no real money. Whether the real GPay/PhonePe app opens in Razorpay's test mode is
  not documented by Razorpay; verify the app hand-off in live mode with a ₹1 payment.
- Cashfree's API details (order and payment endpoints, webhook signature) follow Cashfree's
  2023-08-01 API. Confirm them against a sandbox order before the first live payment.

## Moving to Razorpay's Partner program (Model B) later
`tenant_payment_gateways.auth_mode` is `api_keys` today. For Partner sub-merchants, add a
`partner_oauth` branch in `payment_gateway.build_gateway` (bearer access token, refreshed before
its 90-day expiry; `account_ref` holds the sub-merchant account id) and an onboarding screen that
creates/updates the row. The guest flow, webhook, staff screens and reports do not change.
