"""Tests for print-agent/agent.py — the standalone local print-agent that forwards raw
ESC/POS bytes to a Windows printer queue via the raw spooler API (see agent.py's own
module docstring, and CLAUDE.md §10's "local-agent" connection type).

Two layers are covered:
- `send_raw_bytes_to_windows_printer` itself, with `ctypes.WinDLL` mocked out so these
  run without a real Windows printer queue attached — every OpenPrinter/StartDocPrinter/
  StartPagePrinter/WritePrinter failure mode, plus the partial-write case.
- The HTTP layer (`Handler`), run as a real server on a background thread (see
  conftest.py's `agent_server` fixture) so status codes, JSON bodies, and CORS headers
  are exercised exactly as lib/printAgent.ts's `fetch()` calls hit them.
"""

import base64
import json
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch

import pytest

import agent

# ---------------------------------------------------------------------------
# send_raw_bytes_to_windows_printer
# ---------------------------------------------------------------------------


def _mock_winspool(**overrides) -> MagicMock:
    """A WinDLL("winspool.drv") stand-in where every call succeeds by default —
    pass e.g. `StartDocPrinterW=MagicMock(return_value=0)` to make one step fail.
    """
    winspool = MagicMock()
    winspool.OpenPrinterW.return_value = 1
    winspool.StartDocPrinterW.return_value = 42  # any non-zero job id
    winspool.StartPagePrinter.return_value = 1
    winspool.EndPagePrinter.return_value = 1
    winspool.EndDocPrinter.return_value = 1
    winspool.ClosePrinter.return_value = 1

    def _write_all(h_printer, buf, n, written_ptr):
        # WritePrinter reports bytes written through an out-param — MagicMock can't
        # emulate that on its own, so write through the real byref target ourselves
        # (`ctypes.byref(x)._obj is x` in CPython) to mimic a full, successful write.
        written_ptr._obj.value = n
        return 1

    winspool.WritePrinter.side_effect = _write_all
    for name, value in overrides.items():
        setattr(winspool, name, value)
    return winspool


def test_send_raw_bytes_success():
    winspool = _mock_winspool()
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool) as win_dll:
        agent.send_raw_bytes_to_windows_printer("POS80 Printer", b"hello")

    win_dll.assert_called_once_with("winspool.drv")
    assert winspool.OpenPrinterW.call_args[0][0] == "POS80 Printer"
    winspool.StartDocPrinterW.assert_called_once()
    winspool.StartPagePrinter.assert_called_once()
    winspool.WritePrinter.assert_called_once()
    winspool.EndPagePrinter.assert_called_once()
    winspool.EndDocPrinter.assert_called_once()
    winspool.ClosePrinter.assert_called_once()


def test_send_raw_bytes_open_printer_fails():
    winspool = _mock_winspool(OpenPrinterW=MagicMock(return_value=0))
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool):
        with pytest.raises(OSError, match="Could not open printer"):
            agent.send_raw_bytes_to_windows_printer("Missing Printer", b"hello")

    # Never opened, so nothing downstream should have been touched or closed.
    winspool.StartDocPrinterW.assert_not_called()
    winspool.ClosePrinter.assert_not_called()


def test_send_raw_bytes_start_doc_fails():
    winspool = _mock_winspool(StartDocPrinterW=MagicMock(return_value=0))
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool):
        with pytest.raises(OSError, match="StartDocPrinter failed"):
            agent.send_raw_bytes_to_windows_printer("POS80 Printer", b"hello")

    # Printer was opened, so it must still be closed even though the doc never started.
    winspool.ClosePrinter.assert_called_once()
    winspool.StartPagePrinter.assert_not_called()


def test_send_raw_bytes_start_page_fails():
    winspool = _mock_winspool(StartPagePrinter=MagicMock(return_value=0))
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool):
        with pytest.raises(OSError, match="StartPagePrinter failed"):
            agent.send_raw_bytes_to_windows_printer("POS80 Printer", b"hello")

    # The doc was started, so it must still be ended/closed despite the page failure.
    winspool.EndDocPrinter.assert_called_once()
    winspool.ClosePrinter.assert_called_once()
    winspool.WritePrinter.assert_not_called()


def test_send_raw_bytes_write_printer_fails():
    winspool = _mock_winspool(WritePrinter=MagicMock(return_value=0))
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool):
        with pytest.raises(OSError, match="WritePrinter failed"):
            agent.send_raw_bytes_to_windows_printer("POS80 Printer", b"hello")

    # Every "opened" resource is still torn down despite the mid-job failure.
    winspool.EndPagePrinter.assert_called_once()
    winspool.EndDocPrinter.assert_called_once()
    winspool.ClosePrinter.assert_called_once()


def test_send_raw_bytes_partial_write_raises():
    def _short_write(h_printer, buf, n, written_ptr):
        written_ptr._obj.value = n - 1  # spooler reports success but wrote fewer bytes
        return 1

    winspool = _mock_winspool()
    winspool.WritePrinter.side_effect = _short_write
    with patch.object(agent.ctypes, "WinDLL", return_value=winspool):
        with pytest.raises(OSError, match="Only wrote"):
            agent.send_raw_bytes_to_windows_printer("POS80 Printer", b"hello")


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


def _request(base_url: str, method: str, path: str, body: bytes | None = None) -> tuple[int, HTTPConnection]:
    host, port = base_url.replace("http://", "").split(":")
    conn = HTTPConnection(host, int(port), timeout=5)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    return resp, conn


def _post_json(base_url: str, path: str, payload: dict) -> tuple[int, dict]:
    resp, conn = _request(base_url, "POST", path, json.dumps(payload).encode("utf-8"))
    data = json.loads(resp.read())
    conn.close()
    return resp.status, data


def test_health_endpoint(agent_server):
    resp, conn = _request(agent_server, "GET", "/health")
    body = json.loads(resp.read())
    conn.close()

    assert resp.status == 200
    assert body == {"status": "ok", "agent": "kotmate-print-agent"}


def test_unknown_get_path_404(agent_server):
    resp, conn = _request(agent_server, "GET", "/nope")
    resp.read()
    conn.close()
    assert resp.status == 404


def test_print_success(agent_server):
    with patch.object(agent, "send_raw_bytes_to_windows_printer") as send:
        status, body = _post_json(
            agent_server,
            "/print",
            {"printer_name": "POS80 Printer", "data_base64": base64.b64encode(b"hi").decode()},
        )

    assert status == 200
    assert body == {"status": "printed", "printer_name": "POS80 Printer", "bytes": 2}
    send.assert_called_once_with("POS80 Printer", b"hi")


def test_print_missing_data_base64_400(agent_server):
    status, body = _post_json(agent_server, "/print", {"printer_name": "POS80 Printer"})
    assert status == 400
    assert "Invalid request" in body["detail"]


def test_print_missing_printer_name_400(agent_server):
    status, body = _post_json(agent_server, "/print", {"data_base64": base64.b64encode(b"hi").decode()})
    assert status == 400
    assert "Invalid request" in body["detail"]


def test_print_bad_base64_400(agent_server):
    # 5 characters can never be valid base64 (not a multiple of 4 once unpadded) —
    # guaranteed to raise binascii.Error (a ValueError subclass) regardless of Python
    # version, unlike stray-character inputs which base64 silently tolerates.
    status, body = _post_json(agent_server, "/print", {"printer_name": "X", "data_base64": "abcde"})
    assert status == 400


def test_print_invalid_json_400(agent_server):
    resp, conn = _request(agent_server, "POST", "/print", b"not json at all")
    body = json.loads(resp.read())
    conn.close()
    assert resp.status == 400
    assert "Invalid request" in body["detail"]


def test_print_spooler_failure_502(agent_server):
    with patch.object(
        agent, "send_raw_bytes_to_windows_printer", side_effect=OSError("Could not open printer 'X'")
    ):
        status, body = _post_json(
            agent_server, "/print", {"printer_name": "X", "data_base64": base64.b64encode(b"hi").decode()}
        )

    assert status == 502
    assert body["detail"] == "Could not open printer 'X'"


def test_post_unknown_path_404(agent_server):
    resp, conn = _request(agent_server, "POST", "/wrong-path", b"{}")
    resp.read()
    conn.close()
    assert resp.status == 404


def test_options_cors_preflight(agent_server):
    resp, conn = _request(agent_server, "OPTIONS", "/print")
    resp.read()
    conn.close()
    assert resp.status == 204
    assert resp.getheader("Access-Control-Allow-Origin") == "*"
    assert "POST" in resp.getheader("Access-Control-Allow-Methods")


def test_print_response_has_cors_header(agent_server):
    with patch.object(agent, "send_raw_bytes_to_windows_printer"):
        resp, conn = _request(
            agent_server,
            "POST",
            "/print",
            json.dumps(
                {"printer_name": "POS80 Printer", "data_base64": base64.b64encode(b"hi").decode()}
            ).encode("utf-8"),
        )
        resp.read()
    header = resp.getheader("Access-Control-Allow-Origin")
    conn.close()
    assert header == "*"
