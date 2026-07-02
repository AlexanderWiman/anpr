#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Install ANPR Edge Agent as a Windows service (via NSSM).

.DESCRIPTION
    Installs the agent to C:\Program Files\anpr-edge-agent
    Config/data: C:\ProgramData\anpr-edge-agent

    Requires NSSM: https://nssm.cc/download
    Place nssm.exe in deploy\nssm.exe OR ensure nssm is in PATH.

.EXAMPLE
    .\scripts\install-windows-service.ps1
    .\scripts\install-windows-service.ps1 -NoStart
#>
param(
    [string]$InstallDir = "C:\Program Files\anpr-edge-agent",
    [string]$FromDir = "",
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$ServiceName = "ANPREdgeAgent"
$ConfigDir = "$env:ProgramData\anpr-edge-agent"
$LogDir = "$ConfigDir\logs"

function Write-Step($msg) { Write-Host "[install] $msg" -ForegroundColor Cyan }
function Write-Err($msg) { Write-Host "[install] ERROR: $msg" -ForegroundColor Red; exit 1 }

if (-not $FromDir) {
    $FromDir = Resolve-Path (Join-Path $PSScriptRoot "..")
}

if (-not (Test-Path (Join-Path $FromDir "requirements.txt"))) {
    Write-Err "Invalid source directory: $FromDir"
}

# --- Python ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Err @"
Python not found. Install Python 3.11+ from https://www.python.org/downloads/
Enable 'Add Python to PATH' during installation.
"@
}
Write-Step "Using Python: $($python.Source)"

# --- FFmpeg (recommended for RTSP) ---
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[install] WARNING: ffmpeg not in PATH. RTSP may not work." -ForegroundColor Yellow
    Write-Host "[install] Install: winget install Gyan.FFmpeg  OR  choco install ffmpeg"
}

# --- NSSM ---
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    $bundled = Join-Path $FromDir "deploy\nssm.exe"
    if (Test-Path $bundled) {
        $nssm = Get-Command $bundled
    }
}
if (-not $nssm) {
    Write-Err @"
NSSM not found. Download from https://nssm.cc/download
Extract nssm.exe (win64) to: $FromDir\deploy\nssm.exe
Or add nssm to PATH, then re-run this script.

Alternative (no NSSM): .\scripts\install-windows-task.ps1
"@
}
Write-Step "Using NSSM: $($nssm.Source)"

# --- Install application ---
Write-Step "Installing to $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$exclude = @(".venv", ".git", "__pycache__", "storage", "logs", ".env", ".env.dev")
Get-ChildItem $FromDir | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $InstallDir -Recurse -Force
}

# --- Virtual environment ---
$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Step "Creating virtual environment"
    & $python.Source -m venv (Join-Path $InstallDir ".venv")
}
Write-Step "Installing Python dependencies"
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r (Join-Path $InstallDir "requirements.txt")

# --- Config & data dirs ---
Write-Step "Creating config/data in $ConfigDir"
New-Item -ItemType Directory -Force -Path "$ConfigDir\storage\frames" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigDir\storage\events" | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$envFile = Join-Path $ConfigDir ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $InstallDir "deploy\env.production.windows.example") $envFile
    Write-Host "[install] Created $envFile" -ForegroundColor Yellow
    Write-Host "[install] EDIT before starting: RTSP URL, backend URL, token" -ForegroundColor Yellow
} else {
    Write-Step "Keeping existing config: $envFile"
}

# --- Windows Service via NSSM ---
$runScript = Join-Path $InstallDir "scripts\run-agent.cmd"
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Step "Stopping existing service"
    & $nssm.Source stop $ServiceName 2>$null
    & $nssm.Source remove $ServiceName confirm 2>$null
    Start-Sleep -Seconds 2
}

Write-Step "Registering Windows service: $ServiceName"
& $nssm.Source install $ServiceName $runScript
& $nssm.Source set $ServiceName AppDirectory $InstallDir
& $nssm.Source set $ServiceName DisplayName "ANPR Edge Agent"
& $nssm.Source set $ServiceName Description "Local ANPR plate recognition and event delivery to backend"
& $nssm.Source set $ServiceName Start SERVICE_AUTO_START
& $nssm.Source set $ServiceName AppStdout (Join-Path $LogDir "service-stdout.log")
& $nssm.Source set $ServiceName AppStderr (Join-Path $LogDir "service-stderr.log")
& $nssm.Source set $ServiceName AppRotateFiles 1
& $nssm.Source set $ServiceName AppRotateBytes 10485760
& $nssm.Source set $ServiceName AppExit Default Restart
& $nssm.Source set $ServiceName AppRestartDelay 15000

if (-not $NoStart) {
    Write-Step "Starting service"
    & $nssm.Source start $ServiceName
    Start-Sleep -Seconds 3
    Get-Service $ServiceName
} else {
    Write-Step "Service installed but not started (-NoStart)"
}

Write-Host @"

Installation complete.

  App:     $InstallDir
  Config:  $envFile
  Logs:    $LogDir
  Health:  http://127.0.0.1:8080/health

Commands (PowerShell as Admin):
  Get-Service $ServiceName
  nssm restart $ServiceName
  Get-Content $LogDir\agent.log -Tail 50 -Wait

Edit config then restart:
  notepad $envFile
  nssm restart $ServiceName

Create desktop shortcut for workers:
  .\scripts\install-worker-shortcut.ps1

"@ -ForegroundColor Green
