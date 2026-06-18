# Installerar Python och ffmpeg om de saknas (Windows).
$ErrorActionPreference = "Stop"

function Write-Log([string]$Message) {
    Write-Host "[prerequisites] $Message"
}

function Has-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Has-Winget) {
        Write-Log "Installerar Python via winget..."
        winget install -e --id Python.Python.3.12 `
            --accept-package-agreements --accept-source-agreements
    } else {
        Write-Log "Python saknas. Ladda ner fran https://www.python.org/downloads/"
        Write-Log "Kryssa i 'Add Python to PATH' under installationen."
    }
} else {
    Write-Log "Python — OK"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (Has-Winget) {
        Write-Log "Installerar ffmpeg via winget..."
        winget install -e --id Gyan.FFmpeg `
            --accept-package-agreements --accept-source-agreements
    } else {
        Write-Log "ffmpeg saknas. Installera med: winget install Gyan.FFmpeg"
    }
} else {
    Write-Log "ffmpeg — OK"
}
