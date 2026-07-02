# Installerar Python och ffmpeg om de saknas (Windows).
$ErrorActionPreference = "Continue"

function Write-Log([string]$Message) {
    Write-Host "[prerequisites] $Message"
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
