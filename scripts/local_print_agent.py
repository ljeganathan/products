"""StoreMate TN — Local Print Agent (reference implementation).

Why this exists: browser sandboxing means a normal web page cannot reliably
send raw bytes to a dot-matrix or older LPT/USB thermal printer across all
POS hardware (docs/ARCHITECTURE.md's "Printer strategy"). This tiny local
HTTP server fills that gap on Windows retail PCs — the POS frontend POSTs
an already-built print payload (ESC/POS bytes for thermal, or plain text
for dot-matrix) to this agent, which sends it straight to a Windows
printer's RAW datatype via pywin32.

This is *not* meant to be a production-hardened service: it's a reference
agent a store technician runs on the till PC (ideally as a background/tray
app or a Windows service later). It only binds to localhost, so it is not
reachable from the network.

Usage:
    pip install flask pywin32
    python scripts/local_print_agent.py [--port 9743] [--printer "Printer Name"]

Endpoints:
    GET  /health              -> {"status": "ok"}
    GET  /printers             -> {"default": str|None, "printers": [str, ...]}
    POST /print                 body: {"format": "escpos", "data_base64": "..."}
                                    or  {"format": "text", "data": "..."}
"""

from __future__ import annotations

import argparse
import base64
import sys

from flask import Flask, jsonify, request

try:
    import win32print
except ImportError:  # pragma: no cover - only fails on non-Windows dev machines
    win32print = None

app = Flask(__name__)

# Local-only trust model: this agent binds to 127.0.0.1 and is never
# reachable from the network, so a permissive CORS header is acceptable —
# it only ever answers requests that already made it to this machine's
# loopback interface. Restrict further here if you serve the frontend from
# a fixed, known origin.
ALLOWED_ORIGIN = "*"

DEFAULT_PRINTER_NAME: str | None = None


@app.after_request
def add_cors_headers(response):  # type: ignore[no-untyped-def]
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/print", methods=["OPTIONS"])
@app.route("/health", methods=["OPTIONS"])
@app.route("/printers", methods=["OPTIONS"])
def handle_preflight():  # type: ignore[no-untyped-def]
    return "", 204


@app.route("/health", methods=["GET"])
def health():  # type: ignore[no-untyped-def]
    return jsonify({"status": "ok"})


@app.route("/printers", methods=["GET"])
def list_printers():  # type: ignore[no-untyped-def]
    if win32print is None:
        return jsonify({"error": "pywin32 is not installed / not on Windows"}), 500

    printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
    return jsonify({"default": win32print.GetDefaultPrinter(), "printers": printers})


def _send_raw_bytes(data: bytes, printer_name: str | None) -> None:
    if win32print is None:
        raise RuntimeError("pywin32 is not installed / not on Windows")

    name = printer_name or DEFAULT_PRINTER_NAME or win32print.GetDefaultPrinter()
    handle = win32print.OpenPrinter(name)
    try:
        job = win32print.StartDocPrinter(handle, 1, ("StoreMate TN Receipt", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    _ = job


@app.route("/print", methods=["POST"])
def print_receipt():  # type: ignore[no-untyped-def]
    body = request.get_json(silent=True) or {}
    fmt = body.get("format")
    printer_name = body.get("printer_name")

    if fmt == "escpos":
        data_b64 = body.get("data_base64")
        if not data_b64:
            return jsonify({"error": "data_base64 is required for format=escpos"}), 400
        try:
            data = base64.b64decode(data_b64)
        except (ValueError, TypeError) as exc:
            return jsonify({"error": f"invalid base64 payload: {exc}"}), 400
    elif fmt == "text":
        text = body.get("data")
        if text is None:
            return jsonify({"error": "data is required for format=text"}), 400
        data = text.encode("ascii", errors="replace")
    else:
        return jsonify({"error": "format must be 'escpos' or 'text'"}), 400

    try:
        _send_raw_bytes(data, printer_name)
    except Exception as exc:  # noqa: BLE001 - report any printer/driver failure to the caller
        return jsonify({"error": str(exc)}), 500

    return jsonify({"status": "printed", "bytes": len(data)})


def main() -> None:
    global DEFAULT_PRINTER_NAME

    parser = argparse.ArgumentParser(description="StoreMate TN Local Print Agent")
    parser.add_argument("--port", type=int, default=9743)
    parser.add_argument("--printer", type=str, default=None, help="Printer name to use by default")
    args = parser.parse_args()

    DEFAULT_PRINTER_NAME = args.printer

    if win32print is None:
        print(
            "WARNING: pywin32 is not installed or this isn't Windows — "
            "/print will fail until you run this on a Windows PC with "
            "`pip install pywin32`.",
            file=sys.stderr,
        )

    app.run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
