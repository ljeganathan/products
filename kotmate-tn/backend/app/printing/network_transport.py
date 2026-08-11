import logging
import socket

logger = logging.getLogger("kotmate.printing")

# The de facto "raw"/JetDirect port nearly every network/WiFi ESC/POS thermal printer
# listens on for a direct byte-stream print job — no vendor SDK or driver needed.
DEFAULT_RAW_PORT = 9100


def coerce_port(value: object) -> int:
    """`connection_details.port` arrives from the admin form as a string (Printers
    settings, CLAUDE.md §10) — falls back to the standard raw-print port when blank or
    unparseable rather than raising, since a genuinely wrong port already surfaces as a
    connection failure below.
    """
    try:
        return int(value) if value not in (None, "") else DEFAULT_RAW_PORT
    except (TypeError, ValueError):
        return DEFAULT_RAW_PORT


def send_raw_bytes_over_network(
    ip_address: str | None, port: object, data: bytes, timeout: float = 5.0
) -> str | None:
    """Opens a raw TCP socket to a network/WiFi printer and writes `data` verbatim.
    Returns `None` on success, or a message safe to show the cashier on failure — never
    raises, since a print failure must never block a bill/KOT ticket that's already
    committed (mirrors `lib/printDispatch.ts`'s contract on the frontend). The backend
    container reaches the printer's LAN IP directly (outbound-only, no port publishing
    needed), unlike `usb`/`local_agent` printers which are physically attached to
    whichever machine's browser is running the POS/KOT screen.
    """
    ip = (ip_address or "").strip()
    if not ip:
        return "This printer has no IP address configured — set it in Settings > Printers."
    resolved_port = coerce_port(port)
    try:
        with socket.create_connection((ip, resolved_port), timeout=timeout) as sock:
            sock.sendall(data)
        return None
    except OSError as exc:
        logger.warning("Network print to %s:%s failed: %s", ip, resolved_port, exc)
        reason = exc.strerror or str(exc)
        return f"Couldn't reach the printer at {ip}:{resolved_port} — {reason}"
