# Find a real Python 3.11+ on Windows (ignores Microsoft Store app execution aliases).
param(
    [switch]$Install
)

$ErrorActionPreference = "SilentlyContinue"

function Test-WindowsStoreStub([string]$Path) {
    if (-not $Path) { return $true }
    return $Path -match '\\Microsoft\\WindowsApps\\|\\WindowsApps\\'
}

function Test-RealPython([string]$Path) {
    if (-not $Path) { return $false }
    if (Test-WindowsStoreStub $Path) { return $false }
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $version = & $Path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $version) { return $false }
        $parts = $version.Trim().Split('.')
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        # Prefer 3.11–3.13. Python 3.14+ often lacks wheels for YOLO/torch.
        return ($major -eq 3 -and $minor -ge 11 -and $minor -le 13)
    } catch {
        return $false
    }
}

function Get-PythonCandidates {
    $seen = [System.Collections.Generic.HashSet[string]]::new()
    $list = [System.Collections.Generic.List[string]]::new()

    function Add-Candidate([string]$Path) {
        if (-not $Path) { return }
        $normalized = $Path.Trim()
        if ($seen.Add($normalized)) {
            $list.Add($normalized)
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($flag in @('-3.12', '-3.11', '-3')) {
            $out = & py $flag -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                Add-Candidate $out.Trim()
            }
        }
    }

    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { Add-Candidate $cmd.Source }
    }

    $localApp = $env:LOCALAPPDATA
    $programFiles = ${env:ProgramFiles}
    foreach ($ver in @('312', '313', '311')) {
        Add-Candidate "$localApp\Programs\Python\Python$ver\python.exe"
        if ($programFiles) {
            Add-Candidate "$programFiles\Python$ver\python.exe"
        }
        # Python install manager layout (python.org):
        Add-Candidate "$localApp\Python\pythoncore-3.$($ver.Substring(1))-64\python.exe"
    }

    return $list
}

function Find-Python {
    foreach ($candidate in Get-PythonCandidates) {
        if (Test-RealPython $candidate) {
            return $candidate
        }
    }
    return $null
}

function Install-Python {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }
    & winget install -e --id Python.Python.3.12 `
        --accept-package-agreements `
        --accept-source-agreements | Out-Host
    return ($LASTEXITCODE -eq 0)
}

$found = Find-Python
if (-not $found -and $Install) {
    if (Install-Python) {
        $found = Find-Python
    }
}

if ($found) {
    Write-Output $found
    exit 0
}

exit 1
