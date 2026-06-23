@echo off
REM Quick diagnostics for ANPR on Windows (run on the site PC).
setlocal
set "INSTALL=%LOCALAPPDATA%\anpr-edge-agent"
set "LOG=%INSTALL%\data\logs\agent-startup.log"

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

powershell -NoProfile -Command ^
  "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/api/version' -UseBasicParsing -TimeoutSec 2; Write-Host '[OK] Dashboard svarar:' $r.Content } catch { Write-Host '[FEL] Dashboard svarar inte pa port 8080' }"

powershell -NoProfile -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*anpr-edge-agent*' -and $_.CommandLine -like '*src.main*' }; if ($p) { Write-Host '[OK] ANPR python-process kors (PID' $p.ProcessId ')' } else { Write-Host '[INFO] Ingen ANPR python-process just nu' }"

echo.
echo Skrivbordsgenvagar:
powershell -NoProfile -Command ^
  "Add-Type -AssemblyName Microsoft.VisualBasic; $d = [Environment]::GetFolderPath('Desktop'); Get-ChildItem $d -Filter 'ANPR*' | ForEach-Object { Write-Host ' -' $_.FullName }"

if exist "%LOG%" (
    echo.
    echo Senaste startup-logg:
    powershell -NoProfile -Command "Get-Content '%LOG%' -Tail 12 | ForEach-Object { Write-Host ' ' $_ }"
)

echo.
echo Starta manuellt:
echo   %INSTALL%\scripts\run-agent.cmd
echo.
pause
