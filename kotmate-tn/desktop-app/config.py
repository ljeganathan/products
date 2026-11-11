"""Shared config file handling for the KOTMate desktop app — one JSON file in
%LOCALAPPDATA%, same install-root convention print-agent/agent.py already uses for its
own log directory.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

DEFAULT_SERVER_URL = "https://app.kotmatetn.in"
DEFAULT_EXIT_PIN = "1234"

logger = logging.getLogger("kotmate.desktop")


def install_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "KOTMateTN" / "Desktop" if base else Path(__file__).resolve().parent / "_local"
    root.mkdir(parents=True, exist_ok=True)
    return root


class Config:
    def __init__(self) -> None:
        self.path = install_root() / "config.json"
        self.server_url = DEFAULT_SERVER_URL
        # kiosk_lock takes effect at the *next* launch (the window's frameless/fullscreen
        # mode is set once at creation — see app.py), same as Android's own screen-pin
        # setting being a persisted choice re-asserted at resume, not hot-toggled mid-use.
        self.kiosk_lock = False
        self.exit_pin = DEFAULT_EXIT_PIN
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.server_url = data.get("server_url", DEFAULT_SERVER_URL) or DEFAULT_SERVER_URL
                self.kiosk_lock = bool(data.get("kiosk_lock", False))
                self.exit_pin = str(data.get("exit_pin") or DEFAULT_EXIT_PIN)
            except (json.JSONDecodeError, OSError):
                logger.warning("Couldn't read %s — using defaults", self.path)

    def _persist(self) -> None:
        self.path.write_text(
            json.dumps(
                {"server_url": self.server_url, "kiosk_lock": self.kiosk_lock, "exit_pin": self.exit_pin},
                indent=2,
            ),
            encoding="utf-8",
        )

    def save_server_url(self, server_url: str) -> None:
        self.server_url = server_url.strip() or DEFAULT_SERVER_URL
        self._persist()

    def save_kiosk_lock(self, enabled: bool, exit_pin: str) -> None:
        self.kiosk_lock = enabled
        self.exit_pin = (exit_pin.strip() or DEFAULT_EXIT_PIN) if enabled else self.exit_pin
        self._persist()
