@echo off
REM Double-click to install the lean (production) print-agent build and register it to
REM auto-start at every Windows logon. See ..\README.md for the full setup walkthrough.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
