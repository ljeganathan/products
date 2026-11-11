; KOTMate TN — Combined installer (Inno Setup)
;
; One Setup.exe for a new counter PC that needs both the desktop app (desktop-app/) and
; the local print agent (print-agent/) — instead of running two separate installers.
; This is additive: print-agent/installer/KOTMatePrintAgent.iss and
; desktop-app/installer/KOTMateDesktop.iss still work standalone (e.g. a kitchen-only PC
; that only ever needs the print agent, with no KOTMate window at all).
;
; Reuses the exact same per-user, no-admin-required install model and Scheduled Task
; auto-start logic as KOTMatePrintAgent.iss (see that file's own comments for the
; Scheduled-Task-first/Startup-folder-fallback reasoning) — the print agent's "zero
; manual intervention" auto-start story must hold regardless of which installer put it
; there.
;
; Build: build both .exe's first —
;   cd print-agent  && python installer\build.py
;   cd desktop-app  && pip install -r requirements.txt && python installer\build.py
; then compile this script:
;
;   iscc installer\KOTMateSetup.iss
;
; Produces dist\KOTMateSetup.exe — the one file to hand to a new counter PC.

#define MyAppName "KOTMate"
#define MyAppVersion "1.0"
#define MyAppPublisher "KOTMate TN"
#define MyDesktopExeName "KOTMateDesktop.exe"
#define MyAgentExeName "PrintAgent.exe"
#define MyTaskName "KOTMate Print Agent"
#define MyDefaultPort "9123"

[Setup]
AppId={{9B4E2F7A-6C1D-4A8B-BF3E-7D2C5A9E1B80}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL=https://kotmate.tn
DefaultDirName={localappdata}\KOTMateTN
DefaultGroupName=KOTMate TN
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputBaseFilename=KOTMateSetup
OutputDir=..\dist
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\Desktop\{#MyDesktopExeName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startnow"; Description: "Start {#MyAppName} now"
Name: "autostart"; Description: "Launch {#MyAppName} (the window) automatically when Windows starts"; Flags: unchecked

[Files]
Source: "..\desktop-app\dist\KOTMateDesktop.exe"; DestDir: "{app}\Desktop"; DestName: "{#MyDesktopExeName}"; Flags: ignoreversion
Source: "..\print-agent\dist\KOTMatePrintAgent.exe"; DestDir: "{app}\PrintAgent"; DestName: "{#MyAgentExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Desktop\{#MyDesktopExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\Desktop\{#MyDesktopExeName}"; Tasks: autostart
; The print agent's own startup shortcut only appears when the Scheduled Task
; registration attempt below didn't succeed — otherwise it would start twice at the
; next logon (same reasoning as KOTMatePrintAgent.iss).
Name: "{userstartup}\KOTMate Print Agent"; Filename: "{app}\PrintAgent\{#MyAgentExeName}"; Parameters: "{code:GetAgentArgs}"; Check: ScheduledTaskNotRegistered

[Run]
Filename: "{app}\Desktop\{#MyDesktopExeName}"; Flags: nowait runasoriginaluser; Tasks: startnow
; The print agent always starts right away, regardless of the "startnow" task above —
; it's a silent background service, not something the counter needs to opt into seeing.
Filename: "{app}\PrintAgent\{#MyAgentExeName}"; Parameters: "{code:GetAgentArgs}"; Flags: nowait runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ""{#MyDesktopExeName}"" /F"; Flags: runhidden; RunOnceId: "KillDesktop"
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ""{#MyAgentExeName}"" /F"; Flags: runhidden; RunOnceId: "KillAgent"
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""{#MyTaskName}"""; Flags: runhidden; RunOnceId: "StopTask"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""{#MyTaskName}"""; Flags: runhidden; RunOnceId: "DeleteTask"

[UninstallDelete]
; Wipes both Desktop/ and PrintAgent/ subfolders — config.json, logs, everything —
; same full-cleanup behavior the two standalone installers already have individually.
Type: filesandordirs; Name: "{app}"

[Code]
var
  PortPage: TInputQueryWizardPage;
  ScheduledTaskRegistered: Boolean;

procedure InitializeWizard;
begin
  PortPage := CreateInputQueryPage(wpSelectTasks,
    'Print Agent Port', 'Port the local print agent listens on',
    'Must match the port set on each printer''s "Local Print Agent" connection in ' +
    'KOTMate''s Settings > Printers. Leave this as {#MyDefaultPort} unless you already ' +
    'know this counter needs a different port.');
  PortPage.Add('Port:', False);
  PortPage.Values[0] := '{#MyDefaultPort}';
end;

function GetPort(): String;
begin
  Result := Trim(PortPage.Values[0]);
  if Result = '' then
    Result := '{#MyDefaultPort}';
end;

// [Icons]'s Check: parameter only accepts a bare function name, not an inline
// expression — this is that function for "not ScheduledTaskRegistered".
function ScheduledTaskNotRegistered(): Boolean;
begin
  Result := not ScheduledTaskRegistered;
end;

// Exposed to [Icons]/[Run] via {code:GetAgentArgs} — the exact argument list
// print-agent/agent.py's own argparse expects (see agent.py's main()).
function GetAgentArgs(Param: String): String;
begin
  Result := '--port ' + GetPort();
end;

function TryRegisterScheduledTask(): Boolean;
var
  ResultCode: Integer;
  TaskAction, Params: String;
begin
  // Same Win32 argument-escaping reasoning as KOTMatePrintAgent.iss: Exec() calls
  // CreateProcess directly, so the whole /TR value needs an outer "..." pair, and the
  // exe path itself an inner backslash-escaped \"...\" pair in case the install path
  // has a space in it.
  TaskAction := '\"' + ExpandConstant('{app}\PrintAgent\{#MyAgentExeName}') + '\" ' + GetAgentArgs('');
  Params := '/Create /F /SC ONLOGON /RL LIMITED /TN "{#MyTaskName}" /TR "' + TaskAction + '"';
  Result := Exec(ExpandConstant('{sys}\schtasks.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    and (ResultCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // Clear out any previous install's auto-start registration first (upgrade, port
    // change) so this run can never leave two competing copies registered.
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "{#MyTaskName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/Delete /F /TN "{#MyTaskName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM "{#MyAgentExeName}" /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    ScheduledTaskRegistered := TryRegisterScheduledTask();
  end;
end;
