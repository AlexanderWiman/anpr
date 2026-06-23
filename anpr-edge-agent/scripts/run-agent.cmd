@echo off
REM Wrapper to start ANPR Edge Agent on Windows (user install).
setlocal
cd /d "%~dp0.."
set "INSTALL=%CD%"
set "LOGDIR=%LOCALAPPDATA%\anpr-edge-agent\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set "LOGFILE=%LOGDIR%\agent-startup.log"

>>"%LOGFILE%" echo.
>>"%LOGFILE%" echo === %DATE% %TIME% run-agent.cmd ===

if not exist "%LOCALAPPDATA%\anpr-edge-agent\data\.env" (
    >>"%LOGFILE%" echo ERROR: data\.env missing
    echo ERROR: Config missing. Run launch\Installer.cmd or edit:
    echo %LOCALAPPDATA%\anpr-edge-agent\data\.env
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    >>"%LOGFILE%" echo ERROR: .venv missing
    echo ERROR: ANPR not installed. Run launch\Installer.cmd first.
    pause
    exit /b 1
)

REM Already serving — nothing to do.
powershell -NoProfile -Command ^
  "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/api/version' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1"
if not errorlevel 1 (
    >>"%LOGFILE%" echo Agent already running on port 8080
    exit /b 0
)

REM Stop stale ANPR python processes that are not serving the dashboard.
>>"%LOGFILE%" echo Stopping stale ANPR processes...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*anpr-edge-agent*' -and $_.CommandLine -like '*src.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
>>"%LOGFILE%" echo Starting python -m src.main in %INSTALL%
".venv\Scripts\python.exe" -m src.main >>"%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%
>>"%LOGFILE%" echo Python exited with code %EXITCODE%
exit /b %EXITCODE%
