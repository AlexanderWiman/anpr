@echo off
REM Wrapper to start ANPR Edge Agent on Windows.
REM Used by NSSM service and for manual runs.

setlocal
cd /d "%~dp0.."

REM Load config from ProgramData (production install)
set "CONFIG=%ProgramData%\anpr-edge-agent\.env"
if exist "%CONFIG%" (
    copy /Y "%CONFIG%" ".env" >nul
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found. Run install-windows-service.ps1 first.
    exit /b 1
)

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%

".venv\Scripts\python.exe" -m src.main
