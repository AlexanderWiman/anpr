@echo off
setlocal EnableExtensions
title Installera ANPR

cd /d "%~dp0"

if exist "%~dp0anpr-edge-agent\launch\Installer.cmd" (
  pushd "%~dp0anpr-edge-agent"
  call "%~dp0anpr-edge-agent\launch\Installer.cmd"
  set "EXIT_CODE=%ERRORLEVEL%"
  popd
  exit /b %EXIT_CODE%
)

echo.
echo  Kunde inte hitta anpr-edge-agent\launch\Installer.cmd
echo  Oppna mappen dar du packade upp zip-filen (anpr-main) och kor den harifran.
echo.
pause
exit /b 1
