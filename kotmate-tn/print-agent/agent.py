"""KOTMate TN local print-agent (CLAUDE.md §10 "local-agent" connection type).

Runs on the same Windows machine as a USB/locally-installed printer (e.g. a thermal
receipt printer registered as a normal Windows printer queue via its own driver, such
as "POS80 Printer"). The KOTMate browser tab cannot reach that printer directly, and
the backend container can't either (it's on the counter machine's LAN/USB, not the
server's) — so the browser POSTs the already-rendered raw ESC/POS bytes here, and this
agent forwards them to the Windows print spooler exactly as any other document would be
printed, via the same raw WritePrinter path used by every Windows POS/label-printing
tool (no bundled driver, no admin rights beyond what printing already requires).

Usage:
    python agent.py [--port 9123]

Then in KOTMate's Printers settings, register the bill/KOT printer with connection
type "Local Print Agent" and set its "Windows Printer Name" to the exact name shown in
Windows' printer list (Settings > Bluetooth & devices > Printers & scanners), e.g.
"POS80 Printer".
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import logging
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("kotmate.print_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Only the browser tab serving the POS should be allowed to call this agent — this is a
# local developer/single-counter tool, not a public service, so a wildcard is fine (the
# agent only listens on 127.0.0.1 and is not reachable from the network).
ALLOWED_ORIGIN = "*"


class DOCINFO(ctypes.Structure):
    _fields_ = [
        ("pDocName", wintypes.LPCWSTR),
        ("pOutputFile", wintypes.LPCWSTR),
        ("pDatatype", wintypes.LPCWSTR),
    ]


def send_raw_bytes_to_windows_printer(printer_name: str, data: bytes) -> None:
    """Sends `data` verbatim to a Windows printer queue via the raw spooler API
    (OpenPrinter/StartDocPrinter/WritePrinter) — the same mechanism ESC/POS-aware
    Windows drivers (e.g. "POS80ENG") pass straight through to the physical printer
    without reformatting, which is what lets our server-rendered ESC/POS bytes print
    correctly instead of being interpreted as plain text.
    """
    winspool = ctypes.WinDLL("winspool.drv")

    h_printer = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(h_printer), None):
        raise OSError(f"Could not open printer '{printer_name}' — check the name matches Windows exactly")

    try:
        doc_info = DOCINFO(pDocName="KOTMate TN Bill", pOutputFile=None, pDatatype="RAW")
        job_id = winspool.StartDocPrinterW(h_printer, 1, ctypes.byref(doc_info))
        if job_id == 0:
            raise OSError("StartDocPrinter failed")
        try:
            if not winspool.StartPagePrinter(h_printer):
                raise OSError("StartPagePrinter failed")
            try:
                written = wintypes.DWORD(0)
                buf = ctypes.create_string_buffer(data, len(data))
                if not winspool.WritePrinter(h_printer, buf, len(data), ctypes.byref(written)):
                    raise OSError("WritePrinter failed")
                if written.value != len(data):
                    raise OSError(f"Only wrote {written.value} of {len(data)} bytes")
            finally:
                winspool.EndPagePrinter(h_printer)
        finally:
            winspool.EndDocPrinter(h_printer)
    finally:
        winspool.ClosePrinter(h_printer)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "agent": "kotmate-print-agent"})
        else:
            self._send_json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/print":
            self._send_json(404, {"detail": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            printer_name = body["printer_name"]
            data = base64.b64decode(body["data_base64"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"detail": f"Invalid request: {exc}"})
            return

        try:
            send_raw_bytes_to_windows_printer(printer_name, data)
        except OSError as exc:
            logger.exception("Print job failed")
            self._send_json(502, {"detail": str(exc)})
            return

        self._send_json(200, {"status": "printed", "printer_name": printer_name, "bytes": len(data)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9123)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    logger.info("KOTMate print-agent listening on http://127.0.0.1:%d (Ctrl+C to stop)", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
