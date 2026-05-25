[Setup]
AppName=ChessLens
AppVersion=1.0.0
AppPublisher=sjefenfabian
AppPublisherURL=https://github.com/fabbernn/Chesslens
AppComments=Free offline chess analyzer with AI voice coach
AppReadmeFile=https://github.com/fabbernn/Chesslens#readme
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
Source: "..\LICENSE";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md";          DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\ChessLens";          Filename: "{app}\ChessLens.exe"
Name: "{group}\README";             Filename: "{app}\README.txt"
Name: "{group}\Uninstall ChessLens"; Filename: "{uninstallexe}"
Name: "{commondesktop}\ChessLens";  Filename: "{app}\ChessLens.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\ChessLens.exe"; Description: "Launch ChessLens"; Flags: nowait postinstall skipifsilent
