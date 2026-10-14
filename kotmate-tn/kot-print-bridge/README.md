# KOTMate TN — KOT print bridge

Prints kitchen tickets automatically, with no browser involved. Without this, a ticket
only prints while a POS or Kitchen Display tab is open on the printer's PC, with its
"🖨️ Kitchen printing" switch on. This script does the same job in the background, so an
order placed on a customer's phone prints even if no screen is open or being watched.

It is a companion to `print-agent/` (one folder up), not a replacement for it — the two
run together:

```
Customer's phone  →  KOTMate server  →  this bridge (polls the server)  →  print-agent  →  printer
```

- **This bridge** asks the server every few seconds for new kitchen tickets, and claims
  the right to print each one (the same claim a POS/KOT screen makes, so a ticket is
  never printed twice even if a screen is also open).
- **`print-agent/agent.py`** (one folder up) still has to be running on this PC — it's
  the part that actually talks to the Windows printer. Set that up first; see
  `../print-agent/README.md`.

Only prints a **Local Print Agent** kitchen printer. A Bluetooth/USB/RawBT printer only
works from a real browser tab, and a Wi-Fi/network printer is already printed by the
server itself — this bridge skips both and leaves them as they are today.

## Requirements

- Python 3.9+ (standard library only — nothing to `pip install`).
- `print-agent/agent.py` already running on this same PC, with the kitchen printer
  registered in KOTMate as **Local Print Agent**.
- The tenant must be on the **Pro Max** plan (the KOT screen feature).

## Setup

**1. Create a dedicated login.** In KOTMate, go to Settings → User Management and add a
new user with the **KOT User** role (role code `kitchen`). This role can only see
kitchen tickets, so it's the lowest-privilege login to leave running unattended on a PC.
Write down its login id and password.

**2. Fill in the config.**

```
cd kot-print-bridge
copy config.example.json config.json
```

Edit `config.json`:

| Field | Meaning |
|---|---|
| `api_base` | Your KOTMate address, e.g. `https://app.kotmatetn.in` (production) or `http://localhost:8000` (local Docker). |
| `user_id` / `password` | The login from step 1. |
| `agent_url` | Where `print-agent/agent.py` listens — leave as `http://127.0.0.1:9123` unless you changed its `--port`. |
| `poll_seconds` | How often to check for new tickets. 5 seconds is a sensible default. |
| `location_id` | Leave as `null` to watch every location this tenant has. Set to one location's id (from Settings → Company Master) to watch only that one. |

`config.json` holds a real password — keep this PC physically secure, the same caution
as `print-agent/`. It's already excluded from git.

**3. Run it.**

```
python bridge.py
```

Leave this window open. It logs each ticket it sees and prints, and reconnects and logs
back in by itself if the connection drops or the login session expires.

## Keeping it running in the background

For now, the simplest option is to leave the console window open (minimized) on the PC
that runs `print-agent`. To start it automatically at Windows logon without a visible
window, create a Scheduled Task:

1. Open **Task Scheduler** → **Create Task**.
2. **General**: name it "KOTMate KOT Print Bridge", and tick **Run whether user is
   logged on or not** (or keep it simple with **Run only when user is logged on**).
3. **Triggers** → **New** → **At log on**.
4. **Actions** → **New** → **Start a program**:
   - Program: the full path to `pythonw.exe` (same folder as `python.exe`, but with no
     console window)
   - Arguments: the full path to `bridge.py`
   - Start in: the `kot-print-bridge` folder
5. Save, then log off and back on to confirm it starts and prints.

A packaged `.exe` with a one-click installer (like `print-agent/installer/`) can be
built the same way later if you want it — ask and it can be added.

## If a ticket doesn't print

Check `logs/bridge.log` (next to this script) for the reason. Common ones:

- `Couldn't reach the local print-agent` — `agent.py` isn't running, or the port doesn't
  match `agent_url`.
- `Printer has no Windows Printer Name set` — fill that in under Settings → Printers.
- `needs the Pro Max plan's KOT screen feature` — the tenant's plan doesn't include the
  KOT screen.
- Nothing logged at all for a ticket — another screen (POS or Kitchen Display) already
  claimed and printed it first. That's expected if one is open with printing on; turn its
  switch off if you want this bridge to be the only thing printing.
