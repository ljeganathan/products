# KOTMate Print Agent (Android)

The Android twin of `print-agent/agent.py` (the Windows local print agent) — a
background app that holds direct connections to physical thermal printers over
**Bluetooth, USB, or WiFi/LAN** and exposes them to KOTMate's web app over a tiny local
HTTP server, exactly like the Windows agent does. Built because RawBT (the other
`connection_type` for Android — see `PrintersPage.tsx`) only ever remembers a single
default printer; this app can drive any number of printers from one tablet, each
addressed by name.

It is a completely standalone add-on — **nothing in `backend/` or `frontend/` changes**.
KOTMate already understands "a named printer reachable over a local HTTP agent"
(`connection_type: local_agent`, see `frontend/src/lib/printAgent.ts`); this app just
implements that same protocol on Android instead of Windows.

## Protocol (identical to `print-agent/agent.py`)

- `GET /health` → `200 {"status": "ok", ...}`
- `POST /print` with `{"printer_name": "...", "data_base64": "...", "paper_width_mm": 80}`
  → `200` on success, `400`/`500` with `{"detail": "..."}` on failure.
- The `printer_name` is looked up against whatever printers are configured *in this app*
  — it has nothing to do with Windows printer names; it's just the same field reused as
  a generic "which physical printer" key.

## Setting it up

1. Install the APK on the Android device that's physically near the printer(s).
2. Open the app, grant Bluetooth/notification permissions when asked.
3. Tap **+** to add each printer:
   - **Bluetooth**: pair it in Android's own Bluetooth settings first, then pick it
     from the paired-device list here.
   - **USB**: plug it in (OTG cable if needed), pick it from the attached-device list,
     grant the USB permission prompt.
   - **WiFi**: enter the printer's own IP address and port (almost always `9100`).
   - Give it a **name** — this must exactly match the "Windows Printer Name" field you
     set for this printer in KOTMate's **Settings → Printers** (connection type
     **"Local Print Agent"**), and the **agent port** there must match the port shown
     at the top of this app (`9123` by default).
4. Use the **Test** button on each printer row to confirm the wiring before relying on
   it from KOTMate itself.
5. Leave the app running — it keeps printing in a background service even if you switch
   away, and restarts itself automatically on reboot.

## Building

Standard Gradle/Android Studio project — open `android-print-agent/` in Android
Studio, or from the command line:

```
cd android-print-agent
gradle wrapper --gradle-version 8.7   # one-time, generates the wrapper jar
./gradlew assembleDebug
```

No credentials, secrets, or server configuration are baked into this app — it only
ever talks to whatever KOTMate's web app (running in a browser, a Tauri desktop shell,
or the table-tablet app) sends it on localhost.

## Known limitations (be upfront about these with real printers)

- Bluetooth support targets **Classic/SPP** printers (the vast majority of
  "Bluetooth" thermal receipt printers) — BLE-only printers aren't handled.
- USB support assumes a printer with a plain bulk-OUT endpoint (true for essentially
  every ESC/POS USB printer); it hasn't been tested against real hardware from this
  environment — there's no physical printer or Android device available here to verify
  against. Please test with your actual printers and report anything odd.
- This project could not be compiled in this environment (no Android SDK was
  available) — see the top-level summary for what verification was actually done
  before this was handed to you.
