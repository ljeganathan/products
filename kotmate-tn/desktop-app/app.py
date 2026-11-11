"""KOTMate TN desktop app — a window pointed at KOTMate's own web app, with a system
tray icon for Settings/Reload/Exit. Needs no Rust/Electron/Tauri toolchain: just Python
+ pywebview (wraps the OS's own WebView2 control on Windows) + pystray, matching the
exact same lightweight PyInstaller build already used for print-agent/agent.py, so the
same "no manual setup on a counter PC" story applies here too.

Every role difference (POS vs KOT vs Kiosk, which branch/section) is already handled by
KOTMate's own login and routing — this app is deliberately dumb, same reasoning as
android-staff-app's own doc comment.

Kiosk lock (config.kiosk_lock): the Windows equivalent of the Android apps' "lock this
device" option. There's no OS-level Assigned Access toggle an ordinary app can flip on
its own — that needs separate Group Policy/MDM setup outside this app — so this is the
practical, app-level equivalent: a frameless, fullscreen window with no title bar/close
button, where even opening Settings or exiting requires the configured PIN. Someone with
Task Manager access can still kill the process (same honest caveat as Android's screen
pinning not surviving Task Manager-equivalent access either).

Usage: python app.py
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

import pystray
import webview
from PIL import Image, ImageDraw

from config import Config, install_root

logger = logging.getLogger("kotmate.desktop")

PRINT_AGENT_HEALTH_URL = "http://127.0.0.1:9123/health"
PRINT_AGENT_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "KOTMateTN" / "PrintAgent" / "PrintAgent.exe"

_ASSET_DIR = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
_SETTINGS_HTML_PATH = _ASSET_DIR / "settings.html"
_PIN_HTML_PATH = _ASSET_DIR / "pin.html"


def _configure_logging() -> None:
    log_dir = install_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "desktop.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root_logger.addHandler(stream)


class SettingsApi:
    """Exposed to settings.html as `window.pywebview.api` (pywebview's js_api bridge)."""

    def __init__(self, config: Config, main_window: webview.Window) -> None:
        self._config = config
        self._main_window = main_window

    def get_server_url(self) -> str:
        return self._config.server_url

    def save_server_url(self, url: str) -> bool:
        self._config.save_server_url(url)
        logger.info("Server URL changed to %s", self._config.server_url)
        self._main_window.load_url(self._config.server_url)
        return True

    def get_kiosk_lock(self) -> dict:
        return {"enabled": self._config.kiosk_lock, "exit_pin": self._config.exit_pin}

    def save_kiosk_lock(self, enabled: bool, exit_pin: str) -> bool:
        self._config.save_kiosk_lock(enabled, exit_pin)
        logger.info("Kiosk lock set to %s", enabled)
        return True


def _require_pin_if_locked(config: Config, on_allowed: Callable[[], None]) -> None:
    """Runs `on_allowed` immediately when kiosk lock is off; otherwise opens the PIN
    prompt and only runs it once the correct PIN is entered.
    """
    if not config.kiosk_lock:
        on_allowed()
        return

    # `pin_window` is referenced inside `_Api.check_pin` only once the HTML page's own
    # JS actually calls back into Python (the user submitting a PIN) — by then
    # `create_window` below has already returned and assigned it, so this closure-over-
    # a-not-yet-assigned-name is safe despite the apparent ordering.
    pin_window: webview.Window

    class _Api:
        def check_pin(self, pin: str) -> bool:
            if pin.strip() == config.exit_pin:
                pin_window.destroy()
                on_allowed()
                return True
            return False

    pin_window = webview.create_window(
        "KOTMate Locked",
        url=str(_PIN_HTML_PATH),
        width=320,
        height=220,
        resizable=False,
        on_top=True,
        js_api=_Api(),
    )


def _print_agent_running() -> bool:
    try:
        with urllib.request.urlopen(PRINT_AGENT_HEALTH_URL, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _start_or_locate_print_agent(icon: pystray.Icon) -> None:
    if _print_agent_running():
        icon.notify("The print agent is already running.", "KOTMate")
        return
    if PRINT_AGENT_EXE.exists():
        subprocess.Popen([str(PRINT_AGENT_EXE)], creationflags=subprocess.CREATE_NO_WINDOW)
        icon.notify("Starting the print agent…", "KOTMate")
    else:
        icon.notify(
            "Print agent isn't installed on this PC — install it from print-agent/README.md first.",
            "KOTMate",
        )


def _tray_icon_image() -> Image.Image:
    # A plain generated glyph — no bundled .ico/.png asset needed at all.
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, 61, 61), fill=(31, 122, 85, 255))
    draw.text((20, 18), "K", fill=(255, 255, 255, 255))
    return image


def _run_tray(window: webview.Window, config: Config) -> None:
    def open_settings() -> None:
        webview.create_window(
            "KOTMate Settings",
            url=str(_SETTINGS_HTML_PATH),
            width=420,
            height=420,
            resizable=False,
            js_api=SettingsApi(config, window),
        )

    def do_exit() -> None:
        icon.stop()
        window.destroy()

    def on_open(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        window.show()

    def on_reload(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        window.load_url(config.server_url)

    def on_settings(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _require_pin_if_locked(config, open_settings)

    def on_print_agent(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _start_or_locate_print_agent(icon)

    def on_exit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _require_pin_if_locked(config, do_exit)

    menu = pystray.Menu(
        pystray.MenuItem("Open KOTMate", on_open, default=True),
        pystray.MenuItem("Reload", on_reload),
        pystray.MenuItem("Settings…", on_settings),
        pystray.MenuItem("Check print agent", on_print_agent),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )
    icon = pystray.Icon("kotmate-desktop", _tray_icon_image(), "KOTMate", menu)
    icon.run()


def main() -> None:
    _configure_logging()
    config = Config()
    logger.info("Starting KOTMate desktop, server_url=%s, kiosk_lock=%s", config.server_url, config.kiosk_lock)

    window = webview.create_window(
        "KOTMate",
        url=config.server_url,
        width=1280,
        height=800,
        min_size=(900, 600),
        fullscreen=config.kiosk_lock,
        frameless=config.kiosk_lock,
        easy_drag=False,
    )

    # Closing the window hides it instead of quitting, whether that's a click on the (X)
    # button in normal mode or Alt+F4 in locked/frameless mode — the tray icon is what
    # actually owns the app's lifetime. Returning False here is pywebview's documented
    # way to cancel the close and keep the window (and the whole process) alive.
    def on_closing() -> bool:
        window.hide()
        return False

    window.events.closing += on_closing

    webview.start(_run_tray, (window, config), gui="edgechromium")


if __name__ == "__main__":
    main()
