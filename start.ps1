# PowerShell runner for Personal Finance App
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Menjalankan Personal Finance App (Backend + Expo Go)  " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
wsl bash -c "cd /mnt/e/agy/Finance && /mnt/e/agy/Finance/backend/.venv/bin/python scripts/run_app.py"
