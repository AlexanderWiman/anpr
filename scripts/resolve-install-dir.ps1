# Resolve ANPR install directory on Windows (ProgramData preferred, LOCALAPPDATA legacy).
function Get-AnprInstallDir {
    if ($env:ANPR_INSTALL_DIR) {
        $explicit = $env:ANPR_INSTALL_DIR
        if (Test-Path (Join-Path $explicit "src\main.py")) {
            return $explicit
        }
    }

    $candidates = @(
        (Join-Path $env:ProgramData "anpr-edge-agent"),
        (Join-Path $env:LOCALAPPDATA "anpr-edge-agent")
    )

    foreach ($dir in $candidates) {
        if (Test-Path (Join-Path $dir "src\main.py")) {
            return $dir
        }
    }

    return $candidates[0]
}

if ($MyInvocation.InvocationName -ne '.') {
    Get-AnprInstallDir
}
