@echo off
REM Start ANPR Edge Agent on Windows (delegates to PowerShell, no visible window).
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0run-agent.ps1"
exit /b %ERRORLEVEL%
