<#
.SYNOPSIS
    Removes the KOTMate TN print-agent's auto-start registration (whichever mechanism
    install.ps1 ended up using — Scheduled Task or Startup-folder shortcut) and the
    installed files (%LOCALAPPDATA%\KOTMateTN\PrintAgent), reversing install.ps1.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$TaskName = "KOTMate Print Agent"
$InstallDir = Join-Path $env:LOCALAPPDATA "KOTMateTN\PrintAgent"
$TargetExe = Join-Path $InstallDir "PrintAgent.exe"
$StartupShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\KOTMate Print Agent.lnk"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed Scheduled Task '$TaskName'."
}

if (Test-Path $StartupShortcut) {
    Remove-Item -Path $StartupShortcut -Force
    Write-Host "Removed Startup-folder shortcut."
}

if (Test-Path $TargetExe) {
    Get-Process -Name (Get-Item $TargetExe).BaseName -ErrorAction SilentlyContinue | Stop-Process -Force
}

if (Test-Path $InstallDir) {
    Remove-Item -Path $InstallDir -Recurse -Force
    Write-Host "Removed $InstallDir."
}

Write-Host "Uninstalled."
