@echo off
REM Wrapper to start ANPR Edge Agent on Windows (user install).
setlocal
cd /d "%~dp0.."

set "CONFIG=%LOCALAPPDATA%\anpr-edge-agent\data\.env"
if exist "%CONFIG%" (
    copy /Y "%CONFIG%" ".env" >nul
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: ANPR not installed. Run Installer.cmd first.
    exit /b 1
)

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
".venv\Scripts\python.exe" -m src.main
