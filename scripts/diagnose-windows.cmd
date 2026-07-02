@echo off
REM Quick diagnostics for ANPR on Windows (run on the site PC).
setlocal
set "INSTALL=%LOCALAPPDATA%\anpr-edge-agent"
set "SCRIPTS=%INSTALL%\scripts"

echo.
echo === ANPR diagnostik ===
echo Installationsmapp: %INSTALL%
echo.

if exist "%INSTALL%\data\.env" (
    echo [OK] data\.env finns
) else (
    echo [FEL] data\.env saknas
)

if exist "%INSTALL%\.venv\Scripts\python.exe" (
    echo [OK] Python venv finns
) else (
    echo [FEL] .venv saknas — kor Install ANPR igen
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\diagnose-windows.ps1"

echo.
echo Starta manuellt:
echo   %INSTALL%\scripts\run-agent.cmd
echo.
pause
