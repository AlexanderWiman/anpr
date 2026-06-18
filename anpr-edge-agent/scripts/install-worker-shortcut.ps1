#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Create a desktop shortcut for site workers to start ANPR after reboot.

.EXAMPLE
    .\scripts\install-worker-shortcut.ps1
    .\scripts\install-worker-shortcut.ps1 -InstallDir "C:\Program Files\anpr-edge-agent"
#>
param(
    [string]$InstallDir = "C:\Program Files\anpr-edge-agent",
    [string]$ShortcutName = "Start ANPR"
)

$ErrorActionPreference = "Stop"

$startScript = Join-Path $InstallDir "scripts\start-anpr.cmd"
if (-not (Test-Path $startScript)) {
    $startScript = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\start-anpr.cmd"
    $InstallDir = Split-Path $PSScriptRoot -Parent
}

if (-not (Test-Path $startScript)) {
    Write-Error "start-anpr.cmd not found. Run install-windows-service.ps1 first."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$publicDesktop = "$env:Public\Desktop"
$shortcutPath = Join-Path $publicDesktop "$ShortcutName.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $startScript
$shortcut.WorkingDirectory = $InstallDir
$shortcut.WindowStyle = 1
$shortcut.Description = "Starta ANPR registreringsskyltssystem"
$shortcut.Save()

Write-Host "Desktop shortcut created:" -ForegroundColor Green
Write-Host "  $shortcutPath"
Write-Host ""
Write-Host "Workers: double-click '$ShortcutName', choose site, then press Starta in the browser."

# Optional: auto-launch dashboard app at login (web UI only, worker clicks Start)
$addStartup = Read-Host "Add shortcut to Startup folder (auto-open browser at login)? [y/N]"
if ($addStartup -eq "y" -or $addStartup -eq "Y") {
    $startup = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp"
    $startupLink = Join-Path $startup "$ShortcutName.lnk"
    Copy-Item $shortcutPath $startupLink -Force
    Write-Host "Added to Startup: $startupLink"
}
