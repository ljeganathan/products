<#
.SYNOPSIS
    Installs the KOTMate TN local print-agent so it starts automatically at Windows
    logon — no manual step needed at the counter PC ever again (production feedback:
    "no manual intervention in client... local print agent should run at startup of
    windows").

.DESCRIPTION
    Copies the given print-agent .exe (built by installer\build.py) to
    %LOCALAPPDATA%\KOTMateTN\PrintAgent\PrintAgent.exe and registers it to auto-start
    at every logon, then starts it immediately so the counter can print right away — no
    logout/login needed. Re-running this script (upgrading, changing the port, switching
    variants) safely replaces the previous install.

    Prefers a per-user Scheduled Task (auto-restarts the agent if it ever crashes,
    hidden, no window) — this normally needs no admin rights on a real interactive
    desktop logon. Some locked-down environments (Group Policy restricting Task
    Scheduler, remote/non-interactive sessions) deny that regardless of privilege level;
    if so, this falls back automatically to a Startup-folder shortcut instead
    (%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup — runs at logon too, just
    without the auto-restart-on-crash behavior). Either way, no prompt, no manual choice
    — the script picks whichever mechanism actually works on this machine.

.PARAMETER ExePath
    Path to a built .exe from installer\build.py — KOTMatePrintAgent.exe (lean,
    production counters) or KOTMatePrintAgentEmulate.exe (bundles Pillow, dev/test
    machines only). Defaults to the lean build sitting in ..\dist next to this script.

.PARAMETER Port
    Port the agent listens on. Must match the port configured on each printer's "Local
    Print Agent" connection in KOTMate's Settings > Printers. Default 9123.

.PARAMETER Emulate
    Pass --emulate to the agent at every launch — only meaningful with the
    Pillow-bundled KOTMatePrintAgentEmulate.exe; never use this on a real counter PC.

.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -ExePath ..\dist\KOTMatePrintAgentEmulate.exe -Emulate
#>
[CmdletBinding()]
param(
    [string]$ExePath,
    [int]$Port = 9123,
    [switch]$Emulate
)

$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:LOCALAPPDATA "KOTMateTN\PrintAgent"
$TargetExe = Join-Path $InstallDir "PrintAgent.exe"
$TaskName = "KOTMate Print Agent"
$StartupShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\KOTMate Print Agent.lnk"

if (-not $ExePath) {
    $ExePath = Join-Path $PSScriptRoot "..\dist\KOTMatePrintAgent.exe"
}
if (-not (Test-Path $ExePath)) {
    throw "Can't find '$ExePath'. Build it first: python installer\build.py (see print-agent\README.md)."
}
$ExePath = (Resolve-Path -Path $ExePath).Path

if ($Emulate -and ($ExePath -notlike "*Emulate*")) {
    Write-Warning "-Emulate was passed but '$ExePath' doesn't look like the Pillow-bundled build (KOTMatePrintAgentEmulate.exe) - --emulate will fail at runtime without Pillow bundled in."
}

$ArgumentList = "--port $Port"
if ($Emulate) { $ArgumentList += " --emulate" }

# Clear out any previous install of either kind first — re-running this script (upgrade,
# port change, switching variants, or switching which auto-start mechanism ended up
# being used) must never leave two competing copies running, and the running .exe has to
# actually stop before it can be overwritten below (Windows locks a running .exe's file).
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}
if (Test-Path $StartupShortcut) {
    Remove-Item -Path $StartupShortcut -Force
}
if (Test-Path $TargetExe) {
    Get-Process -Name (Get-Item $TargetExe).BaseName -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path $ExePath -Destination $TargetExe -Force

$AutoStartMethod = $null

try {
    $Action = New-ScheduledTaskAction -Execute $TargetExe -Argument $ArgumentList -WorkingDirectory $InstallDir
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -Hidden

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "Bridges KOTMate TN (browser) to this PC's Windows printer queue. Installed by print-agent/installer/install.ps1 - see kotmate-tn/print-agent/README.md." `
        -ErrorAction Stop | Out-Null

    Start-ScheduledTask -TaskName $TaskName
    $AutoStartMethod = "Scheduled Task '$TaskName' (auto-restarts if it ever crashes)"
} catch {
    # Some environments (Group Policy locking down Task Scheduler for standard users,
    # remote/non-interactive sessions) deny Scheduled Task registration outright,
    # independent of admin rights — fall back to a plain Startup-folder shortcut, which
    # only needs write access to the current user's own Startup folder.
    Write-Warning "Couldn't register a Scheduled Task ($($_.Exception.Message)) - falling back to a Startup-folder shortcut instead."

    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($StartupShortcut)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.Arguments = $ArgumentList
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "KOTMate TN local print-agent - starts automatically at logon."
    $Shortcut.Save()

    Start-Process -FilePath $TargetExe -ArgumentList $ArgumentList -WorkingDirectory $InstallDir
    $AutoStartMethod = "Startup-folder shortcut (no auto-restart-on-crash, but still starts at every logon with no manual step)"
}

Start-Sleep -Seconds 1

$Health = $null
try {
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
} catch {
    Write-Warning "Installed and started, but couldn't reach http://127.0.0.1:$Port/health yet - give it a few more seconds, or check $InstallDir\logs\agent.log."
}

Write-Host ""
Write-Host "KOTMate print-agent installed: $TargetExe"
Write-Host "Auto-start: $AutoStartMethod - no manual step needed again."
if ($Health) {
    Write-Host "Running now: $($Health | ConvertTo-Json -Compress)"
}
Write-Host ""
Write-Host "Next: in KOTMate, Settings > Printers - set connection type 'Local Print Agent', port $Port."
