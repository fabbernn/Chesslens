@echo off
setlocal EnableDelayedExpansion
title ChessLens

color 0A
cls
echo.
echo  ============================================================
echo   ChessLens  -  PySide6 Edition
echo  ============================================================
echo.

:: ── Find Python ───────────────────────────────────────────────────────────
set "PY="
py       --version >nul 2>&1 && set "PY=py"       && goto :py_found
python   --version >nul 2>&1 && set "PY=python"    && goto :py_found
python3  --version >nul 2>&1 && set "PY=python3"   && goto :py_found
py -3.14 --version >nul 2>&1 && set "PY=py -3.14"  && goto :py_found
py -3.13 --version >nul 2>&1 && set "PY=py -3.13"  && goto :py_found
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"  && goto :py_found

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) do if exist %%P ( set "PY=%%~P" & goto :py_found )

color 0C
echo  ERROR: Python not found. Install from https://www.python.org/downloads/
pause & exit /b 1

:py_found
for /f "tokens=2" %%v in ('!PY! --version 2^>^&1') do set PYVER=%%v
echo  Python !PYVER! found  ^(using: !PY!^)
echo.

:: ── Install packages ──────────────────────────────────────────────────────
echo  Installing/updating packages (one-time, may take a few minutes)...
!PY! -m pip install --quiet --upgrade pip 2>nul
!PY! -m pip install --quiet -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo  Package install hit an issue, retrying without --quiet:
    !PY! -m pip install -r "%~dp0requirements.txt"
)
echo  Done.
echo.

:: ── Launch ───────────────────────────────────────────────────────────────
echo  ============================================================
echo   Launching ChessLens...
echo  ============================================================
echo.

cd /d "%~dp0"
!PY! main.py

if errorlevel 1 (
    echo.
    echo  ChessLens exited with an error - see above.
    pause
)
