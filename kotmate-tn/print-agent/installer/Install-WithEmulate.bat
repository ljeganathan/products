@echo off
REM Double-click to install the Pillow-bundled build with --emulate always on — for a
REM dev/test machine only, never a real counter PC. See ..\README.md.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -ExePath "%~dp0..\dist\KOTMatePrintAgentEmulate.exe" -Emulate %*
pause
