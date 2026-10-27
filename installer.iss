#define AppName "Desktop Pet Template"
#define AppVersion "0.1.0"
[Setup]
AppId={{0752B71A-EAD7-4413-BFFB-0AC7A3108492}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\DesktopPetTemplate
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=DesktopPetTemplate-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DesktopPetTemplate.exe
[Files]
Source: "dist\DesktopPetTemplate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\DesktopPetTemplate.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DesktopPetTemplate.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
