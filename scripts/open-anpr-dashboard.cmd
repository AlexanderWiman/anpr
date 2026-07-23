@echo off
REM Start ANPR agent if needed, wait until ready, then open the local dashboard.
setlocal

for /f "delims=" %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0resolve-install-dir.ps1"') do set "INSTALL=%%I"
set "WAIT_PS1=%INSTALL%\scripts\wait-for-agent.ps1"

if not exist "%WAIT_PS1%" (
    echo.
    echo ANPR ar inte installerat. Kor launch\Installer.cmd forst.
    echo.
    pause
    exit /b 1
)

echo.
echo Startar ANPR — vanta upp till 2 minuter...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%WAIT_PS1%" -InstallDir "%INSTALL%" -VisibleWindow
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

start "" "http://127.0.0.1:8080/"
