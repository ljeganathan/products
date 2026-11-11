# KOTMate Table Tablet

A dedicated Android app for a tablet physically mounted at one dine-in table — the
"guest QR ordering" experience, but on a fixture instead of a customer's own phone.

## How it works

1. **First run**: the app shows a "Scan this table's QR code" screen. Staff scan the
   exact same QR code already printed/stuck on that table (the one a customer would
   otherwise scan with their own phone) using the tablet's camera.
2. The scanned URL is saved locally on the device. From then on, the app launches
   straight into that table's ordering page, full screen, with no browser chrome, no
   way to navigate elsewhere, and screen-pinned (Android's built-in kiosk mode) so it
   can't be swiped away to the home screen or another app.
3. **Between customers**: tap the small faded icon in the bottom-right corner →
   **"New customer (reload)"** to reset the screen for the next party. This is a
   deliberate manual staff action, not automatic — the existing guest ordering page is
   a single-page app with no reliable outside signal for "a bill just got paid" without
   changing that app's own code (out of scope for this add-on). As a safety net, the
   tablet also reloads itself automatically every 45 minutes regardless, in case staff
   forget.
4. To move a tablet to a different table (or rebind it after the table's QR is
   reprinted), use the same corner menu → **"Re-bind this tablet to a different
   table"**, then scan the new QR.

## Zero backend/frontend changes

This app is a plain `WebView` pointed at the exact same URL a customer's phone would
open — nothing about the guest ordering flow itself was changed to support this. It
reuses whatever table QR codes `GET /api/v1/tables/.../qr` (or the equivalent
admin/table-master screen) already generates.

## Building

```
cd android-table-tablet
gradle wrapper --gradle-version 8.7   # one-time, generates the wrapper jar
./gradlew assembleDebug
```

## Known limitations

- Screen Pinning (`startLockTask`) is the no-MDM-required kiosk mechanism — a device
  owner/MDM-enrolled rollout could instead make this the one allowed app outright
  (stronger lockdown, harder to escape even with Back+Overview held down), worth
  revisiting if you manage these tablets via an MDM later.
- Could not be compiled or run in this environment (no Android SDK, no real device,
  no camera to test QR scanning against) — see the top-level summary for what
  verification was actually possible.
