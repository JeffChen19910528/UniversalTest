# Builds the portable Windows one-click app: dist/windows/UniversalTest/UniversalTest.exe
# Run from a venv with `.[packaging]` installed (see pyproject.toml).
#
# Usage: powershell -File release/windows/build.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

# Prefer the repo's own venv interpreter if one exists -- PowerShell's
# $ErrorActionPreference does NOT turn a native command's non-zero exit
# code into a terminating error, so calling the wrong interpreter (one
# without PyInstaller installed) would otherwise fail silently and this
# script would print "Built" without having built anything.
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Push-Location $RepoRoot
try {
    & $PythonExe -m PyInstaller `
        (Join-Path $PSScriptRoot "UniversalTest.spec") `
        --distpath (Join-Path $RepoRoot "dist\windows") `
        --workpath (Join-Path $RepoRoot "build\windows") `
        --noconfirm

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $ExePath = Join-Path $RepoRoot "dist\windows\UniversalTest\UniversalTest.exe"
    if (-not (Test-Path $ExePath)) {
        throw "Build reported success but $ExePath was not produced"
    }

    Write-Host "Built: $ExePath"
} finally {
    Pop-Location
}
