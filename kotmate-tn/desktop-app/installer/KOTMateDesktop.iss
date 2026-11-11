; KOTMate TN — Desktop app installer (Inno Setup)
;
; A normal Windows Setup.exe wizard around the standalone .exe installer/build.py already
; produces — same reasoning as print-agent/installer/KOTMatePrintAgent.iss, which this
; mirrors closely (per-user install, no admin rights, optional auto-start task).
;
; Build: install Inno Setup (https://jrsoftware.org/isinfo.php), build the .exe first
; (installer/build.py — see desktop-app/README.md), then compile this script:
;
;   iscc installer\KOTMateDesktop.iss
;
; Produces dist\KOTMateDesktopSetup.exe — the one file to hand to a counter PC.

#define MyAppName "KOTMate"
#define MyAppVersion "1.0"
#define MyAppPublisher "KOTMate TN"
#define MyAppExeName "KOTMateDesktop.exe"
#define MyTaskName "KOTMate Desktop"

[Setup]
AppId={{7C3A1E9B-4F2D-4B6A-9E8C-1A5D3F7B2C60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL=https://kotmate.tn
DefaultDirName={localappdata}\KOTMateTN\Desktop
DefaultGroupName=KOTMate TN
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputBaseFilename=KOTMateDesktopSetup
OutputDir=..\dist
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startnow"; Description: "Start {#MyAppName} now"
; Unchecked by default — unlike the print agent (a silent background service), this is
; a foreground window someone actively looks at, so auto-starting it at every Windows
; logon is the counter's own choice, not assumed.
Name: "autostart"; Description: "Launch {#MyAppName} automatically when Windows starts"; Flags: unchecked

[Files]
Source: "..\dist\KOTMateDesktop.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser; Tasks: startnow

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ""{#MyAppExeName}"" /F"; Flags: runhidden; RunOnceId: "KillDesktop"

[UninstallDelete]
; Wipes the whole install dir including app.py's own rotating log file and config.json
; (%LOCALAPPDATA%\KOTMateTN\Desktop) — same full-cleanup behavior as the print agent's
; own uninstaller.
Type: filesandordirs; Name: "{app}"
