@echo off
title Personal Finance App Runner
echo ========================================================
echo   Menjalankan Personal Finance App (Backend + Expo Go)
echo ========================================================
wsl bash -c "cd /mnt/e/agy/Finance && /mnt/e/agy/Finance/backend/.venv/bin/python scripts/run_app.py"
pause
