$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing $python — create the project venv first."
}
& $python (Join-Path $root "open_hlmv.py") @args
exit $LASTEXITCODE
