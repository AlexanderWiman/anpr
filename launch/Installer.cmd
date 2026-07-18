@echo off
setlocal EnableExtensions
title ANPR Install Wizard
cd /d "%~dp0.."

set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\find-python.ps1"`) do set "PYTHON_EXE=%%P"

if not defined PYTHON_EXE (
  echo.
  echo  Python 3.11-3.13 saknas. Forsoker installera Python 3.12 automatiskt...
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\find-python.ps1" -Install
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\find-python.ps1"`) do set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
  echo.
  echo  Python kunde inte hittas eller installeras.
  echo.
  echo  Gor sa har:
  echo    1. Kor launch\Install-Prerequisites.cmd
  echo    2. Eller ladda ner Python 3.12 fran https://www.python.org/downloads/release/python-31210/
  echo       Kryssa i "Add Python to PATH" under installationen.
  echo       Viktigt: undvik Python 3.14 — ANPR kraver 3.11-3.13.
  echo    3. Stang av Microsoft Store-alias om det stör:
  echo       Installningar - Appar - Avancerade appinstallningar - appkorningalias
  echo       Stang av python.exe och python3.exe dar.
  echo.
  pause
  exit /b 1
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo ffmpeg saknas - forsoker installera automatiskt via winget...
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  )
)

"%PYTHON_EXE%" -c "import fastapi, uvicorn" 2>nul || "%PYTHON_EXE%" -m pip install -q fastapi uvicorn httpx pydantic pydantic-settings python-dotenv

echo.
echo  ANPR Install Wizard - webblasaren oppnas strax...
echo  Lamna detta fonster oppet tills installationen ar klar.
echo.

"%PYTHON_EXE%" -m installer
pause
