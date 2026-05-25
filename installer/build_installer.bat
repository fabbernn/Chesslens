@echo off
setlocal

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if not exist %ISCC% (
    echo ERROR: Inno Setup 6 not found. Download from https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo Building installer...
%ISCC% ChessLens.iss
if %ERRORLEVEL% neq 0 (
    echo Build failed.
    pause
    exit /b 1
)

echo Done. Output: installer\ChessLens_Setup_1.0.0.exe
pause
