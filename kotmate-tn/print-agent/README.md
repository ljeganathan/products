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
- Python 3.9+ on the counter PC (stdlib only — no extra packages to install).

## Run

```
python agent.py
```

Or double-click `start.bat`. Leave the window open — it needs to keep running while
the counter is billing. (To run it automatically at Windows startup, put a shortcut to
`start.bat` in `shell:startup`.)

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
