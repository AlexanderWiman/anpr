@echo off
title ANPR — Installation
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo Python saknas. Installera Python 3.11+ fran python.org
  pause
  exit /b 1
)

python -m installer
if errorlevel 1 python -m installer.cli
pause
