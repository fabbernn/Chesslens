[Setup]
AppName=ChessLens
AppVersion=1.0.0
AppPublisher=sjefenfabian
AppPublisherURL=https://github.com/sjefenfabian/chesslens
DefaultDirName={autopf}\ChessLens
DefaultGroupName=ChessLens
OutputDir=.
OutputBaseFilename=ChessLens_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ChessLens.exe
PrivilegesRequired=lowest

[Files]
Source: "..\dist\ChessLens.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ChessLens"; Filename: "{app}\ChessLens.exe"
Name: "{group}\Uninstall ChessLens"; Filename: "{uninstallexe}"
Name: "{commondesktop}\ChessLens"; Filename: "{app}\ChessLens.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\ChessLens.exe"; Description: "Launch ChessLens"; Flags: nowait postinstall skipifsilent
