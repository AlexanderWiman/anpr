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

REM Already serving — do not kill a running or starting agent.
powershell -NoProfile -Command ^
  "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/api/version' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; ^
   if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*anpr-edge-agent*' -and $_.CommandLine -like '*src.main*' }) { exit 0 }; exit 1"
if not errorlevel 1 exit /b 0

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
".venv\Scripts\python.exe" -m src.main
