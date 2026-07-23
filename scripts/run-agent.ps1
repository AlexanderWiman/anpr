# Start ANPR Edge Agent (Windows). Used by scheduled task and run-agent.cmd.
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "resolve-install-dir.ps1")
$InstallDir = Get-AnprInstallDir
$DataDir = Join-Path $InstallDir "data"
$LogDir = Join-Path $DataDir "logs"
$EnvFile = Join-Path $DataDir ".env"
$LogFile = Join-Path $LogDir "agent-startup.log"
$LockFile = Join-Path $DataDir "run-agent.lock"

function Write-Log([string]$Message) {
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Get-PythonExe {
    foreach ($relative in @(".venv\Scripts\python.exe", "venv\Scripts\python.exe")) {
        $candidate = Join-Path $InstallDir $relative
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Test-AgentUp {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/version" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-StaleAgentProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -like "*anpr-edge-agent*" -and $_.CommandLine -like "*src.main*"
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

try {
    Write-Log "=== run-agent.ps1 install=$InstallDir ==="

    if (-not (Test-Path $EnvFile)) {
        Write-Log "ERROR: missing $EnvFile"
        throw "Konfiguration saknas: $EnvFile"
    }

    $python = Get-PythonExe
    if (-not $python) {
        Write-Log "ERROR: python venv missing under $InstallDir"
        throw "Python-miljo saknas under $InstallDir"
    }

    if (Test-AgentUp) {
        Write-Log "Agent already running on port 8080"
        exit 0
    }

    if (Test-Path $LockFile) {
        $age = (Get-Date) - (Get-Item $LockFile).LastWriteTime
        if ($age.TotalSeconds -lt 120) {
            Write-Log "Another start attempt is in progress (lock file)"
            exit 0
        }
        Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    }

    New-Item -ItemType File -Force -Path $LockFile | Out-Null

    Stop-StaleAgentProcesses
    Start-Sleep -Seconds 1

    $env:ANPR_ENV_FILE = $EnvFile
    $env:PYTHONPATH = $InstallDir
    $env:PYTHONUNBUFFERED = "1"

    Write-Log "Starting $python -m src.main"
    Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "src.main" `
        -WorkingDirectory $InstallDir `
        -WindowStyle Hidden

    exit 0
} catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    if ($env:ANPR_INTERACTIVE -eq "1") {
        Write-Host $_.Exception.Message
    }
    exit 1
} finally {
    if (Test-Path $LockFile) {
        Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    }
}
