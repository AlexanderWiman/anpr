@echo off
setlocal EnableExtensions
title ANPR Manual Update
cd /d "%~dp0.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Python saknas i .venv — kor fran installationsmappen, t.ex. C:\ProgramData\anpr-edge-agent
  pause
  exit /b 1
)

echo Hamtar senaste version fran backend och uppdaterar...
echo Dashboarden stangs av en stund.
"%PYTHON%" -m installer.manual_update_cli
set "RC=%ERRORLEVEL%"

if exist "%CD%\data\local-update.json" del /f /q "%CD%\data\local-update.json"

if %RC% neq 0 (
  echo Uppdatering misslyckades. Se data\logs\remote-update.log
  pause
  exit /b %RC%
)

echo Uppdatering klar. Ladda om dashboarden.
pause
exit /b 0
