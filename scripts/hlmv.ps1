# Launch SDK HLMV on the last compiled playermodel.
# Usage (from repo root):
#   .\scripts\hlmv.ps1
#   .\scripts\hlmv.ps1 tronprogram
#   .\scripts\hlmv.ps1 path\to\model.mdl
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing $Python. Create the project .venv first."
}
Set-Location -LiteralPath $Repo
& $Python -m app.hlmv @args
exit $LASTEXITCODE
