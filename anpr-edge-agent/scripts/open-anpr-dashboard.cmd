@echo off
REM Start ANPR agent if needed, then open the local dashboard.
setlocal
set "INSTALL=%LOCALAPPDATA%\anpr-edge-agent"
set "RUN=%INSTALL%\scripts\run-agent.cmd"

if not exist "%RUN%" (
    echo ANPR ar inte installerat. Kor launch\Installer.cmd forst.
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$ok = $false; try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8080); $ok = $c.Connected; $c.Close() } catch {}; if (-not $ok) { Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', '%RUN%' -WindowStyle Minimized }"

echo Vantar pa ANPR...
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8080/"
