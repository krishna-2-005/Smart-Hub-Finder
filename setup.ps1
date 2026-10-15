# One-time setup: Python virtualenv + dependencies, KML processing, frontend packages.
# Usage (from the project folder):  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== Backend: Python virtual environment" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip --quiet
.\.venv\Scripts\pip install -r requirements.txt --quiet
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created backend\.env from .env.example" }

Write-Host "== Backend: repair + analyse the KML" -ForegroundColor Cyan
.\.venv\Scripts\python -m scripts.process_kml

Write-Host "== Frontend: npm install" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install --no-audit --no-fund

Set-Location $root
Write-Host "`nSetup complete. Start the app with .\start-backend.ps1 and .\start-frontend.ps1 (two terminals)." -ForegroundColor Green
