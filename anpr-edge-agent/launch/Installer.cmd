@echo off
title ANPR Install Wizard
cd /d "%~dp0.."

where python >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo Python saknas - forsoker installera automatiskt via winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Starta om detta fonster om Python inte hittas direkt.
    echo.
  ) else (
    echo Python saknas. Kor launch\Install-Prerequisites.cmd eller installera fran python.org
    pause
    exit /b 1
  )
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo ffmpeg saknas - forsoker installera automatiskt via winget...
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  )
)

python -c "import fastapi, uvicorn" 2>nul || python -m pip install -q fastapi uvicorn httpx pydantic pydantic-settings python-dotenv

echo.
echo  ANPR Install Wizard - webblasaren oppnas strax...
echo  Lamna detta fonster oppet tills installationen ar klar.
echo.

python -m installer
pause
