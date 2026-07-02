@echo off
REM ============================================================
REM  Start ANPR — for site workers
REM  Double-click after reboot. Choose site, then press Start in browser.
REM ============================================================
title ANPR - Registreringsskyltar
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Python environment missing. Run scripts\setup.ps1 or install-windows-service.ps1 first.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0choose-site.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)

if exist "%ProgramData%\anpr-edge-agent\.env" (
    copy /Y "%ProgramData%\anpr-edge-agent\.env" ".env" >nul
)

echo.
echo  ANPR Edge Agent
echo  Opening browser...
echo.
echo  Leave this window open while the system runs.
echo.

start "" "http://localhost:8080"

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
".venv\Scripts\python.exe" -m src.main

pause
