$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path .venv)) {
    & .\scripts\install_windows.ps1
}

& .\.venv\Scripts\python.exe -m prioris.bot.main
