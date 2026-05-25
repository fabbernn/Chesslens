@echo off
REM ==============================================================
REM  ChessLens build script
REM  - Installs deps, builds ChessLens.exe via PyInstaller
REM  - Auto-moves the result to %USERPROFILE%\Documents\ChessLens.exe
REM    so your existing desktop shortcut keeps working
REM ==============================================================
setlocal

echo.
echo  Building ChessLens.exe ...
echo.

REM Make sure dependencies are up to date
py -m pip install --upgrade pip >nul 2>&1
py -m pip install --upgrade -r requirements.txt
py -m pip install --upgrade pyinstaller pillow

REM Clear last build outputs
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

REM Build
py -m PyInstaller ChessLens.spec --noconfirm

if not exist dist\ChessLens.exe (
    echo.
    echo  Build failed - see the messages above.
    echo.
    pause
    exit /b 1
)

REM Replace any existing ChessLens.exe in Documents
set "DEST=%USERPROFILE%\Documents\ChessLens.exe"
if exist "%DEST%" (
    echo  Replacing existing %DEST% ...
    del /q "%DEST%"
)
move /Y "dist\ChessLens.exe" "%DEST%" >nul

REM Clear the stale voice.log so a fresh diagnostic is written on next launch
if exist "%USERPROFILE%\.chesslens\voice.log" (
    del /q "%USERPROFILE%\.chesslens\voice.log"
)

echo.
echo  ============================================================
echo   Build OK
echo   New exe at:  %DEST%
echo   Your desktop shortcut still works.
echo  ============================================================
echo.
echo   If the AI voice still doesn't work, check:
echo     %USERPROFILE%\.chesslens\voice.log
echo   That file will tell us why Kokoro failed to load.
echo.

pause
