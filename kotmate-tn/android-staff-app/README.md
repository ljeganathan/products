# KOTMate Staff App

One generic Android app for any staff-operated device — a POS billing terminal, a
Kitchen Display tablet, or a Kiosk — as a single, common APK. It is intentionally
"dumb": it loads KOTMate's own web app in a full-screen `WebView` and does nothing
role-specific at all, because the web app itself already handles that entirely:

- A `pos_user`/`pos_operator` login already lands on `/pos`.
- A `kitchen` (KOT User) login already lands on `/kot`.
- A Kiosk login already has its own on-device setup screen (branch/section), stored
  in the browser's own `localStorage` exactly as it would be in a normal browser tab.

This app changes none of that — it's a thin shell, not a second implementation of any
of it. **Zero backend/frontend changes.**

## Settings

Tap the small faded icon in the bottom-right corner:

- **Server URL** — defaults to the production app, but can point at a self-hosted/
  on-prem deployment instead.
- **Lock this device to this app** — turns on Android's Screen Pinning for a dedicated
  Kiosk/KDS terminal that should never be switched away from. Leave it off for a
  counter phone/tablet staff also use normally (switching apps, taking calls, etc.).

## What this is *not*

- Not the table tablet (`android-table-tablet/`) — that's for an unattended,
  QR-bound, guest-facing device at one specific dine-in table, with no login at all.
- Not the print agent (`android-print-agent/`) — printing is handled entirely
  server-side or by that separate background app; this one has no printer code in it
  whatsoever.

## Building

```
cd android-staff-app
gradle wrapper --gradle-version 8.7   # one-time, generates the wrapper jar
./gradlew assembleDebug
```

## Known limitations

- Could not be compiled or run in this environment (no Android SDK/device available
  at the time this was written) — see the top-level summary for what verification was
  actually possible.
