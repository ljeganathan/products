; KOTMate TN — Local Print Agent installer (Inno Setup)
;
; A normal Windows Setup.exe wizard around the standalone .exe installer/build.py already
; produces — some shops expect to double-click a familiar "Setup.exe" / Next-Next-Install-
; Finish flow and see the app listed under Settings > Apps, rather than run install.ps1
; from a script. This is an additional front end, not a replacement — install.ps1 /
; Install.bat still work exactly as documented in print-agent/README.md.
;
; Auto-start behavior matches install.ps1 exactly (see its own docstring for why both
; paths exist): try registering a per-user Scheduled Task (fires at every logon, restarts
; the agent automatically if it ever crashes) first; if that's denied (locked-down Group
; Policy, some remote/non-interactive sessions), fall back to a Startup-folder shortcut
; instead. Either way: no prompt, no manual step, and the counter never needs to think
; about this again (production feedback: "no manual intervention in client").
;
; No admin rights required (PrivilegesRequired=lowest): installs to the current user's own
; %LOCALAPPDATA%, same as install.ps1 — not Program Files, which would force elevation.
;
; Build: install Inno Setup (https://jrsoftware.org/isinfo.php), build the two .exe's
; first (installer/build.py — see print-agent/README.md), then compile this script:
;
;   iscc installer\KOTMatePrintAgent.iss
;
; Produces dist\KOTMatePrintAgentSetup.exe — the one file to hand to a new counter PC.

#define MyAppName "KOTMate Print Agent"
#define MyAppVersion "1.0"
#define MyAppPublisher "KOTMate TN"
#define MyAppExeName "PrintAgent.exe"
#define MyTaskName "KOTMate Print Agent"
#define MyDefaultPort "9123"

[Setup]
AppId={{2F6B8C1A-9D4E-4A7B-8C3F-5E1D2A7B9C40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL=https://kotmate.tn
DefaultDirName={localappdata}\KOTMateTN\PrintAgent
DefaultGroupName=KOTMate TN
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputBaseFilename=KOTMatePrintAgentSetup
OutputDir=..\dist
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
; No ARPINSTALLLOCATION-under-Program-Files concerns — per-user LocalAppData install, so
; a standard 32/64-bit architecture switch isn't needed here.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "emulate"; Description: "Install the test/dev build instead (adds --emulate support — renders print jobs to PNG images for testing with no thermal hardware attached, see print-agent/README.md). Never select this on a real counter PC."; Flags: unchecked
Name: "startnow"; Description: "Start {#MyAppName} now"

[Files]
Source: "..\dist\KOTMatePrintAgent.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion; Tasks: not emulate
Source: "..\dist\KOTMatePrintAgentEmulate.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion; Tasks: emulate

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetAgentArgs}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Only created when the Scheduled Task registration attempt (CurStepChanged below)
; didn't succeed — otherwise the agent would start twice at the next logon.
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetAgentArgs}"; Check: ScheduledTaskNotRegistered

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetAgentArgs}"; Flags: nowait runasoriginaluser; Tasks: startnow

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ""{#MyAppExeName}"" /F"; Flags: runhidden; RunOnceId: "KillAgent"
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""{#MyTaskName}"""; Flags: runhidden; RunOnceId: "StopTask"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""{#MyTaskName}"""; Flags: runhidden; RunOnceId: "DeleteTask"

[UninstallDelete]
; Wipes the whole install dir including agent.py's own rotating log file
; (%LOCALAPPDATA%\KOTMateTN\PrintAgent\logs) — same full-cleanup behavior as
; uninstall.ps1's Remove-Item -Recurse -Force.
Type: filesandordirs; Name: "{app}"

[Code]
var
  PortPage: TInputQueryWizardPage;
  ScheduledTaskRegistered: Boolean;

procedure InitializeWizard;
begin
  PortPage := CreateInputQueryPage(wpSelectTasks,
    'Print Agent Port', 'Port the print agent listens on',
    'Must match the port set on each printer''s "Local Print Agent" connection in ' +
    'KOTMate''s Settings > Printers. Leave this as {#MyDefaultPort} unless you already ' +
    'know this counter needs a different port (e.g. a second agent on the same PC).');
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
// agent.py's own argparse expects (see agent.py's main()).
function GetAgentArgs(Param: String): String;
begin
  Result := '--port ' + GetPort();
  if WizardIsTaskSelected('emulate') then
    Result := Result + ' --emulate';
end;

function TryRegisterScheduledTask(): Boolean;
var
  ResultCode: Integer;
  TaskAction, Params: String;
begin
  // Exec() below calls CreateProcess directly (no cmd.exe shell in between), so the
  // command line needs real Win32 argument escaping: the whole /TR value is wrapped in
  // an outer pair of "..." (it contains a space, between the exe path and --port), and
  // the exe path itself gets an inner, backslash-escaped \"...\" pair in case the
  // install path itself has a space (e.g. a Windows username with a space in it) —
  // the standard, if fiddly, way to pass a spaced path *plus* arguments through
  // schtasks.exe's own /TR parsing. /RL LIMITED = standard-user privileges, never
  // elevated — matches install.ps1's non-admin Scheduled Task registration exactly.
  TaskAction := '\"' + ExpandConstant('{app}\{#MyAppExeName}') + '\" ' + GetAgentArgs('');
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
    // Clear out any previous install's auto-start registration first (upgrade,
    // port change, or switching lean/emulate) so this run can never leave two
    // competing copies registered — same reasoning as install.ps1's own cleanup
    // block. schtasks.exe doesn't need {app}\{#MyAppExeName} to already exist to
    // register a task pointing at it, so this can safely run before [Files] below.
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "{#MyTaskName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/Delete /F /TN "{#MyTaskName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM "{#MyAppExeName}" /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    ScheduledTaskRegistered := TryRegisterScheduledTask();
  end;
end;
