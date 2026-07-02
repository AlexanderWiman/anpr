#Requires -Version 5.1
<#
.SYNOPSIS
    Merge .env.example with a site profile into .env
#>
param(
    [string]$InstallDir = (Split-Path $PSScriptRoot -Parent)
)

Set-Location $InstallDir

function Merge-Profile {
    param([string]$SiteFile)
    if (-not (Test-Path ".env.example")) {
        Write-Error "Missing .env.example"
    }
    if (-not (Test-Path $SiteFile)) {
        Write-Error "Missing site profile: $SiteFile"
    }
    $content = Get-Content ".env.example" -Raw
    $content += "`n`n# Site profile: $SiteFile`n"
    $content += Get-Content $SiteFile -Raw
    Set-Content -Path ".env" -Value $content -NoNewline
    Write-Host "Using $SiteFile" -ForegroundColor Green
}

if ($env:ANPR_SITE_PROFILE) {
    Merge-Profile "sites\$($env:ANPR_SITE_PROFILE).env"
    exit 0
}

$profiles = @(Get-ChildItem "sites\*.env" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike "*.example" } |
    Sort-Object Name)

if ($profiles.Count -eq 0) {
    Write-Host ""
    Write-Host "  Inga site-profiler i sites\*.env"
    Write-Host "  Kopiera sites\falun.env.example till sites\falun.env"
    Write-Host ""
    if (Test-Path ".env") { exit 0 }
    Copy-Item ".env.example" ".env"
    exit 0
}

if ($profiles.Count -eq 1) {
    Merge-Profile ("sites\" + $profiles[0].Name)
    exit 0
}

Write-Host ""
Write-Host "  Valj anlaggning:"
Write-Host ""
for ($i = 0; $i -lt $profiles.Count; $i++) {
    Write-Host ("    {0}) {1}" -f ($i + 1), $profiles[$i].BaseName)
}
Write-Host ""
$choice = Read-Host "  Val"
$idx = [int]$choice - 1
if ($idx -lt 0 -or $idx -ge $profiles.Count) {
    Write-Error "Ogiltigt val"
}
Merge-Profile ("sites\" + $profiles[$idx].Name)
