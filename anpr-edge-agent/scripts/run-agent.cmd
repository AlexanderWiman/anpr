@echo off
REM Wrapper to start ANPR Edge Agent on Windows (user install).
setlocal
cd /d "%~dp0.."

if not exist "%LOCALAPPDATA%\anpr-edge-agent\data\.env" (
    echo ERROR: Config missing. Run launch\Installer.cmd or edit:
    echo %LOCALAPPDATA%\anpr-edge-agent\data\.env
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: ANPR not installed. Run launch\Installer.cmd first.
    exit /b 1
)

powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*anpr-edge-agent*' -and $_.CommandLine -like '*src.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
".venv\Scripts\python.exe" -m src.main
