#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Uninstall ANPR Edge Agent Windows service or scheduled task.

.EXAMPLE
    .\scripts\uninstall-windows-service.ps1
    .\scripts\uninstall-windows-service.ps1 -PurgeData
#>
param(
    [switch]$PurgeData,
    [string]$InstallDir = "C:\Program Files\anpr-edge-agent"
)

$ServiceName = "ANPREdgeAgent"
$TaskName = "ANPREdgeAgent"
$ConfigDir = "$env:ProgramData\anpr-edge-agent"

# NSSM service
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    $bundled = "C:\Program Files\anpr-edge-agent\deploy\nssm.exe"
    if (Test-Path $bundled) { $nssm = Get-Command $bundled }
}

if ($nssm) {
    & $nssm.Source stop $ServiceName 2>$null
    & $nssm.Source remove $ServiceName confirm 2>$null
}

# Scheduled task
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Application files
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Removed: $InstallDir"
}

if ($PurgeData -and (Test-Path $ConfigDir)) {
    Remove-Item $ConfigDir -Recurse -Force
    Write-Host "Removed: $ConfigDir"
} else {
    Write-Host "Config/data kept at: $ConfigDir (use -PurgeData to remove)"
}

Write-Host "Uninstall complete."
