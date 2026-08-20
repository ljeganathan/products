# KOTMate TN — Local Print Agent

Bridges the KOTMate browser tab to a printer that's physically attached to the counter
PC (USB thermal/dot-matrix printer registered as a normal Windows printer queue).
Neither the browser nor the backend server can reach that printer directly, so this
small local service listens on `127.0.0.1` and forwards print jobs to the Windows
spooler using the printer's own driver — no bundled printer driver, no extra
permissions beyond normal printing.

## Requirements

- Windows, with the printer already installed as a normal Windows printer (driver
  installed, visible under **Settings > Bluetooth & devices > Printers & scanners**).

## Install on a counter PC (recommended)

The counter PC doesn't need Python installed at all — `installer/` packages the agent
into a standalone `.exe` and sets it to start automatically at every Windows logon, so
once it's installed nobody at the counter ever has to think about it again (no
double-clicking a shortcut every morning, no window to remember to leave open).

**One-time setup, from a machine with Python** (doesn't have to be the counter PC — copy
the built `.exe` over afterward):

```
cd print-agent
pip install -r requirements-dev.txt -r installer\requirements-build.txt
python installer\build.py
```

Produces `dist\KOTMatePrintAgent.exe` (lean, no Pillow — this is the one for a real
counter) and `dist\KOTMatePrintAgentEmulate.exe` (bundles Pillow, so `--emulate` works
with nothing else to install — for a dev/test machine, never a real counter).

**On the counter PC**, copy the `installer\` folder (with the built `.exe` alongside it
in `dist\`) over and double-click **`Install.bat`**. That's the entire install — it:

- copies the `.exe` to `%LOCALAPPDATA%\KOTMateTN\PrintAgent\`
- registers it to start at every Windows logon (a Scheduled Task when the machine allows
  it, so a crash auto-restarts it; a Startup-folder shortcut otherwise — either way, no
  prompt, and it just picks whichever works)
- starts it immediately, so the counter can print right away without logging out first

Re-running `Install.bat` (e.g. after `build.py` produces a new version) safely replaces
the previous install — always idempotent, safe to run again. `Uninstall.bat` reverses it
completely. See `installer\install.ps1 -?` / `installer\uninstall.ps1 -?` for the
`-Port`/`-ExePath`/`-Emulate` parameters if you need a non-default port or the Pillow
build.

**Prefer a familiar Setup.exe wizard instead?** `installer\KOTMatePrintAgent.iss` builds
the same install (copy the .exe, register auto-start, start it immediately) as a normal
Windows installer — download [Inno Setup](https://jrsoftware.org/isdl.php) (free), build
both `.exe`'s as above, then either run `iscc installer\KOTMatePrintAgent.iss` or open the
`.iss` in the Inno Setup IDE and press F9. Produces `dist\KOTMatePrintAgentSetup.exe` — one
file, double-click, Next → Next → Install → Finish, shows up under Settings > Apps with a
real Uninstall entry. Same port prompt and lean/emulate choice as `install.ps1`'s
parameters, just as wizard pages/checkboxes instead of command-line flags.

Diagnosing a windowless instance: check
`%LOCALAPPDATA%\KOTMateTN\PrintAgent\logs\agent.log` (rotating, keeps the last 3×2MB) —
there's no console window to read once it's running via the installer.

## Run from source (development)

```
python agent.py
```

Or double-click `start.bat`. Leave the window open — it needs to keep running while
the counter is billing. Requires Python 3.9+ (stdlib only for this normal, real-printer
code path — no extra packages to install).

## Configure in KOTMate

In **Settings > Printers**, add/edit the bill (and/or KOT) printer:
- Connection: **Local Print Agent**
- Windows Printer Name: the exact name shown in Windows' printer list, e.g.
  `POS80 Printer`

The agent defaults to port `9123`; if you change `--port` here, use the same port in
the printer's connection settings.

## Verify it's running

```
curl http://127.0.0.1:9123/health
```

Should return `{"status": "ok", "agent": "kotmate-print-agent"}`.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

Runs entirely without a real printer or Windows print queue — `ctypes.WinDLL` is mocked
for the spooler-level tests, and the HTTP-layer tests run the real `Handler` on a
background thread against an OS-assigned localhost port.

## Testing prints locally — no thermal hardware needed (`--emulate`)

You don't need a real printer, WebUSB, or any special hardware to check what a bill/KOT
ticket/report will look like. Run the agent in **emulate mode** instead of the normal
mode: every print job KOTMate sends is rendered to a PNG image on disk (using the exact
same ESC/POS command subset the backend emits — bold, double-size text, alignment, the
raster logo/QR/Tamil-name images, and the cut line) instead of being sent to a real
Windows printer queue.

This only covers the **Local Print Agent** connection type (`local_agent`). WebUSB
(`usb`) genuinely needs a real USB device Chrome can enumerate — there's no
software-only way to fake that from the browser, so it isn't testable this way.

### 1. Install dependencies

```
cd print-agent
pip install -r requirements-dev.txt
```

(This adds Pillow, needed only for `--emulate`'s image rendering — the normal
real-printer code path stays stdlib-only.)

### 2. Run the agent in emulate mode

```
python agent.py --emulate
```

Leave this window open. You'll see:

```
EMULATE MODE — print jobs will be rendered to PNG in C:\...\print-agent\emulated_prints instead of a real printer
KOTMate print-agent listening on http://127.0.0.1:9123 (Ctrl+C to stop)
```

(Pass a custom folder with `python agent.py --emulate C:\path\to\folder` if you don't
want the default `./emulated_prints`.)

### 3. Register a test printer in KOTMate

In the running app (local Docker stack or wherever you're testing), go to
**Settings > Printers** and add/edit a printer:

- Connection: **Local Print Agent**
- Windows Printer Name: anything you like, e.g. `Emulator` — in emulate mode this name
  is never actually looked up in Windows, it's only used to label the saved PNG filename
- Target: Bill / KOT / Reports
- **Paper Width**: whichever preset (58mm/80mm/241mm) or custom mm value you actually
  want to verify — the saved PNG is rendered at this exact physical width (58mm renders
  narrow, 80mm wider, 241mm a long dot-matrix strip), the same as the backend's own
  formatting, so what you see is what that paper size would really produce

### 4. Trigger a print from KOTMate

Finalize a bill, send a KOT ticket, use **Test Print** on the printer you just
registered, or print a report from the Reports page. Each one POSTs to the agent, which:

- saves a PNG named `<timestamp>_<printer name>.png` into the emulate folder
- opens it automatically in your default image viewer (Windows only; if nothing opens,
  just browse to the folder)

Verify visually: table number is the dominant element, CGST/SGST print as two separate
lines, Round Off always shows, the QR code renders and looks scannable, Tamil item names
appear correctly on bills/KOT tickets (rasterized) but not on reports (reports are plain
text, so Tamil shows as tofu boxes there — that's correct, matching what a real printer
without a Tamil code page would also show), and nothing gets truncated at whichever
paper-width preset you configured.

### 5. Switch back to a real printer

Stop the emulate-mode agent (Ctrl+C) and start it normally:

```
python agent.py
```

No changes needed in KOTMate itself — the printer's connection settings (name, target,
paper width) work the same either way; only the agent's own `--emulate` flag decides
whether jobs go to a real Windows queue or a PNG file.
