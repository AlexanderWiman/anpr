@echo off
setlocal EnableExtensions
title Installera ANPR

cd /d "%~dp0"

if not exist "%~dp0launch\Installer.cmd" (
  echo.
  echo  Kunde inte hitta launch\Installer.cmd
  echo.
  pause
  exit /b 1
)

call "%~dp0launch\Installer.cmd"
exit /b %ERRORLEVEL%
