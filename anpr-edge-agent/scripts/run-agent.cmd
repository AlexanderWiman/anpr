@echo off
REM Wrapper to start ANPR Edge Agent on Windows (user install).
setlocal
cd /d "%~dp0.."
set "INSTALL=%CD%"
set "SCRIPTS=%~dp0"
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
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%test-agent-up.ps1"
if not errorlevel 1 (
    >>"%LOGFILE%" echo Agent already running on port 8080
    exit /b 0
)

REM Stop stale ANPR python processes that are not serving the dashboard.
>>"%LOGFILE%" echo Stopping stale ANPR processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%stop-stale-agent.ps1" >nul 2>&1

set PYTHONUNBUFFERED=1
set PYTHONPATH=%CD%
>>"%LOGFILE%" echo Starting python -m src.main in %INSTALL%
".venv\Scripts\python.exe" -m src.main >>"%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%
>>"%LOGFILE%" echo Python exited with code %EXITCODE%
exit /b %EXITCODE%
