#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Install ANPR Edge Agent as a scheduled task (starts at boot, no NSSM needed).

.EXAMPLE
    .\scripts\install-windows-task.ps1
#>
param(
    [string]$InstallDir = "C:\Program Files\anpr-edge-agent",
    [string]$FromDir = ""
)

$ErrorActionPreference = "Stop"
$TaskName = "ANPREdgeAgent"
$ConfigDir = "$env:ProgramData\anpr-edge-agent"

function Write-Step($msg) { Write-Host "[install] $msg" -ForegroundColor Cyan }
function Write-Err($msg) { Write-Host "[install] ERROR: $msg" -ForegroundColor Red; exit 1 }

if (-not $FromDir) {
    $FromDir = Resolve-Path (Join-Path $PSScriptRoot "..")
}

# Reuse file install logic — call service installer in no-start mode without NSSM section
# Simpler: duplicate minimal install steps

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { Write-Err "Python not found" }

Write-Step "Installing to $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$exclude = @(".venv", ".git", "__pycache__", "storage", "logs", ".env", ".env.dev")
Get-ChildItem $FromDir | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $InstallDir -Recurse -Force
}

$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python.Source -m venv (Join-Path $InstallDir ".venv")
}
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r (Join-Path $InstallDir "requirements.txt")

New-Item -ItemType Directory -Force -Path "$ConfigDir\storage\frames" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigDir\storage\events" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigDir\logs" | Out-Null

$envFile = Join-Path $ConfigDir ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $InstallDir "deploy\env.production.windows.example") $envFile
}

$runScript = Join-Path $InstallDir "scripts\run-agent.cmd"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $runScript -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Description "ANPR Edge Agent — local plate recognition" | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host @"

Scheduled task installed and started.

  Task:    $TaskName
  Config:  $envFile
  Health:  http://127.0.0.1:8080/health

Commands:
  Get-ScheduledTask -TaskName $TaskName
  Stop-ScheduledTask -TaskName $TaskName
  Start-ScheduledTask -TaskName $TaskName

"@ -ForegroundColor Green
