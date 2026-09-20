#ifndef StagingDir
  #error StagingDir must name a verified, assembled preview bundle.
#endif

[Setup]
AppId={{9405B46D-2519-4880-A026-AB787878F862}
AppName=Stick Balancing — Prototype
AppVersion=0.1.0
AppPublisher=Stick Balancing
DefaultDirName={localappdata}\Programs\StickBalancing
DefaultGroupName=Stick Balancing
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
WizardStyle=modern
OutputDir=output
OutputBaseFilename=StickBalancing-Prototype-Setup
Compression=lzma2/fast
SolidCompression=yes
UninstallDisplayIcon={app}\StickBalancing.exe
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; The staging tree contains the desktop app, workers/, trainer/runtime, configs/ and notices/.
Source: "{#StagingDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Main shortcut — launches the desktop application.
Name: "{autoprograms}\Stick Balancing"; Filename: "{app}\StickBalancing.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Stick Balancing"; Filename: "{app}\StickBalancing.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; Flags: unchecked

; ---------------------------------------------------------------------------
; Experiments live in Unity persistentDataPath ({localappdata}\...\experiments).
; The uninstaller must NEVER remove them automatically.
; A separate voluntary cleanup is the user's responsibility.
; ---------------------------------------------------------------------------
