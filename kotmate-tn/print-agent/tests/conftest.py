import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

# `agent.py` lives one directory up from here, as a standalone script rather than a
# package — insert its directory onto sys.path so `import agent` resolves regardless of
# where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent  # noqa: E402


@pytest.fixture
def agent_server():
    """Runs the real `agent.Handler` on an OS-assigned localhost port in a background
    thread — exercises the actual HTTP request/response wiring (status codes, JSON
    bodies, CORS headers) the way a browser tab (lib/printAgent.ts) really hits it,
    rather than calling handler methods directly.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
