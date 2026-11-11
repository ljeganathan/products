# KOTMate Desktop

A Windows desktop app for POS/KDS/Kiosk counters that prefer an installed app over a
browser tab — just a window pointed at KOTMate's own web app, with a system tray icon
for **Settings** (change the server URL), **Reload**, **Check print agent**, and
**Exit**. Every role difference (POS vs KOT vs Kiosk) is already handled by KOTMate's
own login and routing — this app has no role-specific logic at all, same reasoning as
`android-staff-app/`.

Built with Python + [pywebview](https://pywebview.flowrl.com/) (wraps the OS's own
WebView2/Edge control on Windows) instead of Electron/Tauri — no Rust or C++ build
toolchain needed, just the same lightweight PyInstaller pipeline already used for
`print-agent/`. **Zero backend/frontend changes.**

## Using it

- The window opens pointed at `https://app.kotmatetn.in` by default.
- Closing the window (the X button) doesn't quit the app — it just hides it. The tray
  icon (bottom-right of the taskbar) is what actually controls the app:
  - **Open KOTMate** — show the window again.
  - **Reload** — reload the current page (same as a browser refresh).
  - **Settings…** — change the server URL (e.g. to point at a self-hosted/on-prem
    deployment instead of the SaaS URL). Saves and reloads automatically.
  - **Check print agent** — pings `print-agent`'s local health endpoint and offers to
    start it if it's installed but not running.
  - **Exit** — actually quits.

## Kiosk lock

Settings has a **"Lock this device to this app"** option — the Windows equivalent of
the Android apps' own kiosk-lock toggle. There's no OS-level "Assigned Access" switch an
ordinary app can flip on its own (that needs separate Group Policy/MDM setup outside
this app), so this is the practical, app-level equivalent: once enabled (takes effect
the *next* time the app starts), the window opens full screen with no title bar, no
close/minimize button, and even Alt+F4 just hides it instead of closing it — only the
tray icon can exit, and both **Settings…** and **Exit** then require the PIN set when
you turned the lock on. Someone with Task Manager access can still kill the process —
same honest limitation Android's own screen pinning has against its equivalent.

## Printing

This app has no printer code in it at all — printing is handled entirely server-side,
or by the separate `print-agent/` background app (already its own installer, already
auto-starts at login). Install that separately if this counter has a local/USB/Bluetooth
printer attached.

## Building

```
cd desktop-app
pip install -r requirements.txt
python installer/build.py
```

Produces `dist/KOTMateDesktop.exe`. Then, to get a proper `Setup.exe` installer (install
[Inno Setup](https://jrsoftware.org/isinfo.php) first):

```
iscc installer\KOTMateDesktop.iss
```

Produces `dist/KOTMateDesktopSetup.exe` — the one file to hand to a counter PC. Per-user
install (`%LOCALAPPDATA%\KOTMateTN\Desktop`), no admin rights needed, same convention as
`print-agent/`'s own installer.

## Known limitations

- No auto-updater — unlike the originally-planned Tauri version, there's no built-in
  "check GitHub Releases and self-update" mechanism here. Updating means building a new
  `.exe`/installer and re-running it on each counter PC (same as `print-agent/` already
  works today). Worth adding later if this becomes a real pain point.
- Could not be built or run in this environment end-to-end against a live printer or
  real counter hardware — see the top-level summary for what verification was actually
  possible (a real local build/run was done; no physical device testing).
