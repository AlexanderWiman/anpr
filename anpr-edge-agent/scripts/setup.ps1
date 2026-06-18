#Requires -Version 5.1
<#
.SYNOPSIS
    First-time setup on Windows (Python venv + YOLO model)
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host "=== ANPR Edge Agent — setup ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}

& ".venv\Scripts\pip.exe" install -q --upgrade pip
& ".venv\Scripts\pip.exe" install -q -r requirements.txt -r requirements-ai.txt -r requirements-ocr.txt

if (-not (Test-Path "models\plate_yolov8.pt")) {
    Write-Host "Downloading YOLO plate model..."
    bash scripts/download-yolo-model.sh 2>$null
    if (-not (Test-Path "models\plate_yolov8.pt")) {
        $url = "https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt"
        New-Item -ItemType Directory -Force -Path models | Out-Null
        Invoke-WebRequest -Uri $url -OutFile "models\plate_yolov8.pt"
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "  1. Copy sites\falun.env.example to sites\falun.env (edit RTSP URL)"
Write-Host "  2. Edit .env with ANPR_AGENT_TOKEN"
Write-Host "  3. Double-click Start ANPR shortcut or run scripts\start-anpr.cmd"
