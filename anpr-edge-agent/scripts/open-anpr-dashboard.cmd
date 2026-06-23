@echo off
REM Start ANPR agent if needed, wait until ready, then open the local dashboard.
setlocal
set "INSTALL=%LOCALAPPDATA%\anpr-edge-agent"
set "WAIT_PS1=%INSTALL%\scripts\wait-for-agent.ps1"

if not exist "%WAIT_PS1%" (
    echo ANPR ar inte installerat. Kor launch\Installer.cmd forst.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%WAIT_PS1%"
if errorlevel 1 (
    pause
    exit /b 1
)

start "" "http://127.0.0.1:8080/"
