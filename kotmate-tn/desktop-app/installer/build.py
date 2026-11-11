"""Builds a standalone Windows executable of the desktop app via PyInstaller — mirrors
print-agent/installer/build.py exactly, same reasoning: no "install Python first" step
for whoever sets up a counter PC.

Run on a Windows machine, from the desktop-app/ folder:

    pip install -r requirements.txt
    python installer/build.py

Produces desktop-app/dist/KOTMateDesktop.exe — one self-contained .exe, `--onefile
--noconsole` (no console window pops up, same as print-agent's own build).
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

_INSTALLER_DIR = Path(__file__).resolve().parent  # desktop-app/installer
_APP_DIR = _INSTALLER_DIR.parent  # desktop-app
_APP_SCRIPT = _APP_DIR / "app.py"
_DIST_DIR = _APP_DIR / "dist"
_WORK_DIR = _APP_DIR / "build"

_NAME = "KOTMateDesktop"


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Build this on Windows — the resulting .exe only runs there anyway.")

    PyInstaller.__main__.run(
        [
            str(_APP_SCRIPT),
            "--onefile",
            "--noconsole",
            "--name",
            _NAME,
            "--distpath",
            str(_DIST_DIR),
            "--workpath",
            str(_WORK_DIR),
            "--specpath",
            str(_INSTALLER_DIR),
            # settings.html and pin.html are both loaded by path at runtime (app.py's
            # _SETTINGS_HTML_PATH/_PIN_HTML_PATH) — must be bundled as data files, not
            # left to the unfrozen source tree, or the PIN prompt 404s once kiosk lock
            # is on (ERR_FILE_NOT_FOUND) even though everything else works fine.
            "--add-data",
            f"{_APP_DIR / 'settings.html'};.",
            "--add-data",
            f"{_APP_DIR / 'pin.html'};.",
            "--icon",
            str(_APP_DIR / "assets" / "icon.ico"),
        ]
    )
    exe_path = _DIST_DIR / f"{_NAME}.exe"
    if not exe_path.exists():
        raise SystemExit(f"PyInstaller reported success but {exe_path} is missing — check the log above.")
    print(f"\nBuilt: {exe_path}")
    print("Next: compile installer/KOTMateDesktop.iss with Inno Setup to produce a Setup.exe.")


if __name__ == "__main__":
    main()
