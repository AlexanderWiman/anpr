# Installerar Python, ffmpeg och VC++ om de saknas (Windows).
$ErrorActionPreference = "Continue"

function Write-Log([string]$Message) {
    Write-Host "[prerequisites] $Message"
}

function Test-VcRedistInstalled {
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    )
    foreach ($key in $keys) {
        try {
            $installed = (Get-ItemProperty -Path $key -ErrorAction Stop).Installed
            if ($installed -eq 1) {
                return $true
            }
        } catch {
        }
    }
    return $false
}

function Install-VcRedist {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Log "Installerar Microsoft Visual C++ Redistributable (kravs for PyTorch/OCR)..."
        winget install -e --id Microsoft.VCRedist.2015+.x64 `
            --accept-package-agreements --accept-source-agreements
        return
    }

    $url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    $installer = Join-Path $env:TEMP "vc_redist.x64.exe"
    Write-Log "winget saknas — laddar ner VC++ Redistributable x64..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
        Write-Log "Installerar VC++ Redistributable (tyst)..."
        $proc = Start-Process -FilePath $installer -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
        if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 1638) {
            Write-Log "VC++-installation avslutades med kod $($proc.ExitCode)."
        }
    } catch {
        Write-Log "Kunde inte installera VC++ automatiskt. Ladda ner manuellt:"
        Write-Log $url
    } finally {
        Remove-Item $installer -ErrorAction SilentlyContinue
    }
}

$findPython = Join-Path $PSScriptRoot "find-python.ps1"

$python = & $findPython
if (-not $python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Log "Installerar Python via winget..."
        & $findPython -Install | Out-Null
        $python = & $findPython
    }
}

if ($python) {
    Write-Log "Python — OK ($python)"
} else {
    Write-Log "Python saknas. Ladda ner fran https://www.python.org/downloads/"
    Write-Log "Kryssa i 'Add Python to PATH' under installationen."
    Write-Log "Stang av Store-alias: Installningar - Appar - Avancerade appinstallningar - appkorningalias"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Log "Installerar ffmpeg via winget..."
        winget install -e --id Gyan.FFmpeg `
            --accept-package-agreements --accept-source-agreements
    } else {
        Write-Log "ffmpeg saknas. Installera med: winget install Gyan.FFmpeg"
    }
} else {
    Write-Log "ffmpeg — OK"
}

if (Test-VcRedistInstalled) {
    Write-Log "Visual C++ Redistributable — OK"
} else {
    Install-VcRedist
    if (Test-VcRedistInstalled) {
        Write-Log "Visual C++ Redistributable — OK"
    } else {
        Write-Log "VC++ Redistributable saknas fortfarande — OCR kan faila tills den ar installerad."
    }
}
