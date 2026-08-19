"""Builds two standalone Windows executables of the print-agent via PyInstaller — the
whole point is that a counter PC needs **zero manual setup**: no "install Python first",
no `pip install`, nothing to type. Whoever is provisioning a new location just runs
`install.ps1` (same folder) once with the built .exe already sitting next to it.

Run on a Windows machine, from anywhere:

    pip install pyinstaller
    python print-agent/installer/build.py

Produces, under `print-agent/dist/`:
- `KOTMatePrintAgent.exe`        — lean, stdlib-only (matches agent.py's normal
  real-printer code path — no Pillow bundled, so `--emulate` isn't usable with this one).
- `KOTMatePrintAgentEmulate.exe` — bundles Pillow, so `--emulate` (print-agent/README.md)
  works with no extra install — meant for a dev/test machine, not a production counter.

Both are built `--onefile --noconsole`: one self-contained .exe, no window pops up when
Windows launches it at logon (install.ps1 registers it as a Scheduled Task). agent.py's
own rotating file log (`%LOCALAPPDATA%\\KOTMateTN\\PrintAgent\\logs\\agent.log`) is the
only trail while it's running windowless — check that file if a printer stops working.
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

_INSTALLER_DIR = Path(__file__).resolve().parent  # print-agent/installer
_AGENT_DIR = _INSTALLER_DIR.parent  # print-agent
_AGENT_SCRIPT = _AGENT_DIR / "agent.py"
_DIST_DIR = _AGENT_DIR / "dist"
_WORK_ROOT = _AGENT_DIR / "build"

_LEAN_NAME = "KOTMatePrintAgent"
_EMULATE_NAME = "KOTMatePrintAgentEmulate"


def _build(name: str, extra_args: list[str]) -> Path:
    PyInstaller.__main__.run(
        [
            str(_AGENT_SCRIPT),
            "--onefile",
            "--noconsole",
            "--name",
            name,
            "--distpath",
            str(_DIST_DIR),
            "--workpath",
            str(_WORK_ROOT / name),
            "--specpath",
            str(_INSTALLER_DIR),
            *extra_args,
        ]
    )
    exe_path = _DIST_DIR / f"{name}.exe"
    if not exe_path.exists():
        raise SystemExit(f"PyInstaller reported success but {exe_path} is missing — check the log above.")
    return exe_path


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Build this on Windows — the resulting .exe only runs there anyway.")

    print(f"Building {_LEAN_NAME} (lean, no Pillow — production counter PCs)...")
    lean_exe = _build(_LEAN_NAME, ["--exclude-module", "PIL"])

    print(f"\nBuilding {_EMULATE_NAME} (bundles Pillow — dev/test machines)...")
    emulate_exe = _build(_EMULATE_NAME, ["--hidden-import", "escpos_render"])

    print(f"\nBuilt:\n  {lean_exe}\n  {emulate_exe}")
    print("\nNext: installer/install.ps1 -ExePath <one of the above> installs + auto-starts it.")


if __name__ == "__main__":
    main()
