# Freeze the desktop hallway (PyInstaller one-file).
# Usage (from repo root):
#   .\scripts\packaging\freeze.ps1
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing $Python. Create the project .venv first."
}
Set-Location -LiteralPath $Repo
& $Python (Join-Path $Repo "scripts\packaging\freeze.py")
exit $LASTEXITCODE
