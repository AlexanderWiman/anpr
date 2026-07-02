# ANPR Windows diagnostics (called from diagnose-windows.cmd).
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\anpr-edge-agent"
)

$ErrorActionPreference = "SilentlyContinue"
$logFile = Join-Path $InstallDir "data\logs\agent-startup.log"

try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/version" -UseBasicParsing -TimeoutSec 2
    Write-Host "[OK] Dashboard svarar:" $response.Content
} catch {
    Write-Host "[FEL] Dashboard svarar inte pa port 8080"
}

$proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        $_.CommandLine -like "*anpr-edge-agent*" -and $_.CommandLine -like "*src.main*"
    } |
    Select-Object -First 1

if ($proc) {
    Write-Host "[OK] ANPR python-process kors (PID $($proc.ProcessId))"
} else {
    Write-Host "[INFO] Ingen ANPR python-process just nu"
}

Write-Host ""
Write-Host "Skrivbordsgenvagar:"
$desktop = [Environment]::GetFolderPath("Desktop")
Get-ChildItem $desktop -Filter "ANPR*" -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host " - $($_.FullName)" }

if (Test-Path $logFile) {
    Write-Host ""
    Write-Host "Senaste startup-logg:"
    Get-Content $logFile -Tail 12 | ForEach-Object { Write-Host " $_" }
}
