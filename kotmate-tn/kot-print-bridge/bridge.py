#!/usr/bin/env python3
"""KOTMate TN — KOT print bridge.

Prints kitchen tickets automatically, with no browser involved at all. Without this, a
KOT ticket only prints while a POS or Kitchen Display tab is open on the same PC as the
printer, with its "Kitchen printing" switch on (see KotDisplayPage.tsx / POSLayoutRouter.tsx).
This script does the same job from the command line, so it works even if no screen is open.

It logs in once, then repeatedly asks the server for each watched location's open kitchen
tickets, claims any ticket nobody has printed yet (the same POST /kot/tickets/{id}/claim-print
a POS/KOT screen uses — see backend/app/services/kot_service.py's claim_kot_print), and hands
the job to the local print-agent (print-agent/agent.py), which must already be running on
this same PC with the printer installed.

Only prints a "Local Print Agent" (connection_type "local_agent") kitchen printer. A
Bluetooth/USB/RawBT printer is reachable only from a real browser, and a Wi-Fi/network
printer is already printed by the server itself — neither needs this bridge.

Standard library only, same as print-agent/agent.py — nothing to `pip install`.

Usage:
    python bridge.py [--config config.json]

See README.md for setup (the config file, and a dedicated low-privilege login to run this
with).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_AGENT_URL = "http://127.0.0.1:9123"
DEFAULT_POLL_SECONDS = 5
# How often to re-check the tenant's location list, in case one is added — cheap to ask
# more often, but no need to.
LOCATIONS_REFRESH_SECONDS = 300

logger = logging.getLogger("kot-print-bridge")


def _setup_logging(log_dir: Path) -> None:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "bridge.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Couldn't open a log file in %s — continuing with console logging only", log_dir)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"No config file at {path}.\n"
            "Copy config.example.json to config.json next to this script and fill in your own values."
        )
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    missing = [key for key in ("api_base", "user_id", "password") if not config.get(key)]
    if missing:
        raise SystemExit(f"config.json is missing: {', '.join(missing)}")
    config.setdefault("agent_url", DEFAULT_AGENT_URL)
    config.setdefault("poll_seconds", DEFAULT_POLL_SECONDS)
    config["api_base"] = config["api_base"].rstrip("/")
    config["agent_url"] = config["agent_url"].rstrip("/")
    return config


class ApiError(Exception):
    """`status` is 0 for a connection failure (couldn't reach the server at all)."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


def _request(
    method: str, url: str, *, token: str | None = None, body: dict | None = None, timeout: float = 10.0
) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - fixed KOTMate host
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        detail = None
        try:
            detail = json.loads(raw).get("detail") if raw else None
        except (json.JSONDecodeError, AttributeError):
            pass
        raise ApiError(exc.code, detail or exc.reason) from exc
    except urllib.error.URLError as exc:
        raise ApiError(0, str(exc.reason)) from exc


class Session:
    """Logs in once and keeps a usable access token, logging in again on a 401 (the
    access token expires after 30 minutes — see backend ACCESS_TOKEN_EXPIRE_MINUTES)."""

    def __init__(self, api_base: str, user_id: str, password: str) -> None:
        self._api_base = api_base
        self._user_id = user_id
        self._password = password
        self._access_token: str | None = None

    def login(self) -> None:
        logger.info("Logging in as %s", self._user_id)
        result = _request(
            "POST",
            f"{self._api_base}/api/v1/auth/login",
            body={"user_id": self._user_id, "password": self._password},
        )
        self._access_token = result["access_token"]
        logger.info("Logged in (role: %s)", result.get("role"))

    def call(self, method: str, path: str, *, body: dict | None = None) -> Any:
        if self._access_token is None:
            self.login()
        try:
            return _request(method, f"{self._api_base}{path}", token=self._access_token, body=body)
        except ApiError as exc:
            if exc.status == 401:
                logger.info("Access token expired — logging in again")
                self.login()
                return _request(method, f"{self._api_base}{path}", token=self._access_token, body=body)
            raise


def forward_to_local_agent(agent_url: str, job: dict[str, Any]) -> None:
    printer_name = (job.get("connection_details") or {}).get("windows_printer_name")
    if not printer_name:
        logger.warning(
            "Printer has no Windows Printer Name set — nothing to forward (set it in Settings > Printers)"
        )
        return
    body = {
        "printer_name": printer_name,
        "data_base64": job["data_base64"],
        "paper_width_mm": job.get("paper_width_mm"),
    }
    try:
        _request("POST", f"{agent_url}/print", body=body, timeout=10.0)
        logger.info("Printed via local agent (%s)", printer_name)
    except ApiError as exc:
        if exc.status == 0:
            logger.error(
                "Couldn't reach the local print-agent at %s — make sure agent.py is running on this PC",
                agent_url,
            )
        else:
            logger.error("Local print-agent rejected the job: %s", exc.detail)


def _ticket_label(ticket: dict[str, Any]) -> str:
    return ticket.get("ticket_number") or str(ticket["id"]).split("-")[0]


class LocationWatcher:
    """Tracks one location's open kitchen tickets and claims/prints any new one."""

    def __init__(self, session: Session, agent_url: str, location_id: str, location_name: str) -> None:
        self._session = session
        self._agent_url = agent_url
        self.location_id = location_id
        self.location_name = location_name
        # None until the first successful poll — that poll's tickets are the baseline
        # (already open, not new), the same rule the browser's catch-up print uses.
        self._seen: set[str] | None = None

    def poll(self) -> None:
        tickets = self._session.call("GET", f"/api/v1/kot/tickets/active?location_id={self.location_id}")
        if self._seen is None:
            self._seen = {t["id"] for t in tickets}
            logger.info("%s: watching (%d ticket(s) already open)", self.location_name, len(self._seen))
            return
        for ticket in tickets:
            ticket_id = ticket["id"]
            if ticket_id in self._seen or ticket.get("is_pending_takeaway"):
                continue
            self._seen.add(ticket_id)
            self._claim_and_print(ticket)

    def _claim_and_print(self, ticket: dict[str, Any]) -> None:
        label = _ticket_label(ticket)
        try:
            job = self._session.call("POST", f"/api/v1/kot/tickets/{ticket['id']}/claim-print")
        except ApiError as exc:
            logger.error("%s: couldn't ask to print ticket %s: %s", self.location_name, label, exc.detail)
            return
        if job is None:
            # Already claimed by a POS/Kitchen Display screen, or not a browser-printed
            # connection type (a Wi-Fi printer is already printed by the server itself).
            return
        if job.get("connection_type") != "local_agent":
            logger.info(
                "%s: ticket %s is for a %s printer, not this bridge — skipping",
                self.location_name,
                label,
                job.get("connection_type"),
            )
            return
        logger.info("%s: printing ticket %s", self.location_name, label)
        forward_to_local_agent(self._agent_url, job)


def run(config: dict[str, Any]) -> None:
    session = Session(config["api_base"], config["user_id"], config["password"])
    session.login()

    watchers: dict[str, LocationWatcher] = {}
    last_locations_refresh = 0.0
    requested_location_id = config.get("location_id")

    while True:
        now = time.monotonic()
        if now - last_locations_refresh > LOCATIONS_REFRESH_SECONDS or not watchers:
            try:
                locations = session.call("GET", "/api/v1/locations")
            except ApiError as exc:
                logger.error("Couldn't load locations: %s — retrying shortly", exc.detail)
                time.sleep(config["poll_seconds"])
                continue
            if requested_location_id:
                locations = [loc for loc in locations if loc["id"] == requested_location_id]
            for loc in locations:
                if loc["id"] not in watchers:
                    watchers[loc["id"]] = LocationWatcher(
                        session, config["agent_url"], loc["id"], loc["name"]
                    )
            last_locations_refresh = now

        for watcher in watchers.values():
            try:
                watcher.poll()
            except ApiError as exc:
                if exc.status == 403:
                    logger.error(
                        "%s: %s — this bridge needs the Pro Max plan's KOT screen feature turned on",
                        watcher.location_name,
                        exc.detail,
                    )
                else:
                    logger.error("%s: couldn't check tickets: %s", watcher.location_name, exc.detail)
            except Exception:  # noqa: BLE001 - one bad poll must never stop the whole bridge
                logger.exception("%s: unexpected error while polling", watcher.location_name)

        time.sleep(config["poll_seconds"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KOTMate TN — prints kitchen tickets automatically, no browser needed."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    _setup_logging(Path(__file__).resolve().parent / "logs")
    config = load_config(args.config)
    logger.info("KOTMate KOT print bridge starting — server: %s", config["api_base"])
    try:
        run(config)
    except KeyboardInterrupt:
        logger.info("Stopped")
    except ApiError as exc:
        # Most likely a wrong user_id/password, or the server address is wrong — this
        # happens before the main loop's own per-poll error handling takes over, so it
        # needs its own clean message instead of a raw traceback.
        logger.error("Couldn't start: %s", exc.detail)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
