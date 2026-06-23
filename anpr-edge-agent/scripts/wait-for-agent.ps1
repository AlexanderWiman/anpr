# Wait for ANPR web dashboard on 127.0.0.1:8080; start agent if needed.
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\anpr-edge-agent",
    [int]$TimeoutSeconds = 120,
    [switch]$VisibleWindow
)

$ErrorActionPreference = "SilentlyContinue"
$runScript = Join-Path $InstallDir "scripts\run-agent.cmd"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$restartAfter = (Get-Date).AddSeconds(25)

function Test-AgentUp {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/version" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-AgentProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object {
            $_.CommandLine -like "*anpr-edge-agent*" -and $_.CommandLine -like "*src.main*"
        } |
        Select-Object -First 1
}

function Stop-AgentProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object {
            $_.CommandLine -like "*anpr-edge-agent*" -and $_.CommandLine -like "*src.main*"
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Start-AgentProcess {
    if ($VisibleWindow) {
        # Keep window open so startup errors are visible (/k).
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$runScript`""
    } else {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$runScript`"" -WindowStyle Minimized
    }
}

if (-not (Test-Path $runScript)) {
    Write-Host ""
    Write-Host "ANPR ar inte installerat. Kor launch\Installer.cmd forst."
    exit 1
}

if (Test-AgentUp) {
    exit 0
}

if (-not (Get-AgentProcess)) {
    Write-Host "Startar ANPR..."
    Start-AgentProcess
} else {
    Write-Host "ANPR startar, vantar..."
}

while ((Get-Date) -lt $deadline) {
    if (Test-AgentUp) {
        exit 0
    }

    if ((Get-Date) -gt $restartAfter -and (Get-AgentProcess)) {
        Write-Host "ANPR svarar inte — startar om..."
        Stop-AgentProcess
        Start-Sleep -Seconds 2
        Start-AgentProcess
        $restartAfter = (Get-Date).AddSeconds(90)
    }

    Start-Sleep -Seconds 2
}

$logFile = Join-Path $InstallDir "data\logs\agent-startup.log"
Write-Host ""
Write-Host "ANPR svarar inte pa http://127.0.0.1:8080"
Write-Host ""
Write-Host "1. Kor manuellt (lamna fonstret oppet):"
Write-Host "   $runScript"
Write-Host ""
if (Test-Path $logFile) {
    Write-Host "2. Senaste rader i loggen:"
    Get-Content $logFile -Tail 8 | ForEach-Object { Write-Host "   $_" }
}
Write-Host ""
Write-Host "3. Dubbelklicka pa ANPR pa skrivbordet (inte en gammal webblasargenvag)."
exit 1
