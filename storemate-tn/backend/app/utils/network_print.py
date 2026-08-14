import base64
import binascii
import logging
import socket

logger = logging.getLogger("storemate.printing")

# The de facto "raw"/JetDirect port nearly every network/WiFi ESC/POS thermal
# printer listens on for a direct byte-stream print job — no vendor SDK or
# driver needed. Mirrors the same convention used for KOTMate TN's printers.
DEFAULT_RAW_PORT = 9100


def _coerce_port(value: object) -> int:
    """`connection_details.port` arrives from the admin form as a string —
    falls back to the standard raw-print port when blank or unparseable
    rather than raising, since a genuinely wrong port already surfaces as a
    connection failure below."""
    try:
        return int(value) if value not in (None, "") else DEFAULT_RAW_PORT
    except (TypeError, ValueError):
        return DEFAULT_RAW_PORT


def send_raw_bytes_over_network(
    ip_address: object, port: object, data_base64: str, timeout: float = 5.0
) -> str | None:
    """Opens a raw TCP socket to a network/WiFi printer and writes the
    decoded bytes verbatim. Returns `None` on success, or a message safe to
    show the cashier on failure — never raises, since a print failure must
    never block a bill that's already been finalized (mirrors the frontend
    print-dispatch contract in features/pos/printDispatch.ts). The backend
    reaches the printer's IP directly, unlike `webusb`/`local_agent`/
    `bluetooth`/`rawbt` printers which are physically attached to (or paired
    with) whichever machine's browser is running the POS screen — this
    assumes the backend can route to that IP (same LAN, or a port forwarded
    to it from the internet)."""
    ip = str(ip_address or "").strip()
    if not ip:
        return "This printer has no IP address configured — set it in Settings > Printers."

    try:
        data = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError):
        return "The print job data was malformed."

    resolved_port = _coerce_port(port)
    try:
        with socket.create_connection((ip, resolved_port), timeout=timeout) as sock:
            sock.sendall(data)
        return None
    except OSError as exc:
        logger.warning("Network print to %s:%s failed: %s", ip, resolved_port, exc)
        reason = exc.strerror or str(exc)
        return f"Couldn't reach the printer at {ip}:{resolved_port} — {reason}"
