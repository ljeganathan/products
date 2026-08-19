@echo off
REM Double-click to remove the print-agent's auto-start registration and installed files.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
pause
