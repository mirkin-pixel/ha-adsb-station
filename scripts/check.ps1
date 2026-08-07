# Runs what CI runs of the code itself: ruff, mypy, then the tests with coverage.
# The other two workflow jobs, hassfest and HACS validation, read the manifest
# and the repository layout rather than the code, and need a container.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { $python = "python" }

    Write-Host "== ruff ==" -ForegroundColor Cyan
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "== mypy ==" -ForegroundColor Cyan
    & $python -m mypy
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "== pytest ==" -ForegroundColor Cyan
    & $python -m pytest --cov --cov-report=term-missing
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
