$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if ($env:PYTHON_BIN) {
    & $env:PYTHON_BIN -m venv .venv
} else {
    py -3.11 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -e ".[dev]"

if (-not (Test-Path config.toml)) {
    Copy-Item config.example.toml config.toml
}

Write-Host "PRIORIS installed."
Write-Host "Edit config.toml, then run .\scripts\run_windows.ps1"
