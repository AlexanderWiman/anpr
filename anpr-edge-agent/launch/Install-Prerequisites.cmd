@echo off
title ANPR - Installera forutsattningar
cd /d "%~dp0.."

echo.
echo  Installerar Python och ffmpeg om de saknas...
echo  (kan ta nagra minuter forsta gangen)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\install-prerequisites.ps1"
echo.
pause
