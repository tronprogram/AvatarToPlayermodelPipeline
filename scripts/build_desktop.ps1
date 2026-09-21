# Freeze run_desktop.py with PyInstaller (one-file).
# Usage (from repo root):
#   .\scripts\build_desktop.ps1
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing $Python. Create the project .venv first."
}
Set-Location -LiteralPath $Repo
& $Python -m PyInstaller --noconfirm --clean (Join-Path $Repo "desktop.spec")
exit $LASTEXITCODE
