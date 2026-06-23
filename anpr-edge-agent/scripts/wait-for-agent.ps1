# Wait for ANPR web dashboard on 127.0.0.1:8080; start agent if needed.
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\anpr-edge-agent",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "SilentlyContinue"
$runScript = Join-Path $InstallDir "scripts\run-agent.cmd"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

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

if (-not (Test-Path $runScript)) {
    Write-Host "ANPR ar inte installerat. Kor launch\Installer.cmd forst."
    exit 1
}

if (-not (Test-AgentUp)) {
    if (-not (Get-AgentProcess)) {
        Write-Host "Startar ANPR..."
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$runScript`"" -WindowStyle Minimized
    } else {
        Write-Host "ANPR startar, vantar..."
    }

    while ((Get-Date) -lt $deadline) {
        if (Test-AgentUp) {
            exit 0
        }
        Start-Sleep -Seconds 2
    }

    Write-Host ""
    Write-Host "ANPR svarar inte pa http://127.0.0.1:8080"
    Write-Host "Kolla det minimerade fonstret eller kor:"
    Write-Host "  $runScript"
    exit 1
}

exit 0
