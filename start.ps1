# PowerShell runner for the Personal Finance App (backend + Expo Go)
Set-Location $PSScriptRoot

$python = if (Test-Path "backend/.venv/bin/python") {
    "backend/.venv/bin/python"
} else {
    "python"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Menjalankan Personal Finance App (Backend + Expo Go)  " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

& $python scripts/run_app.py