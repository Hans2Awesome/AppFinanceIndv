@echo off
title Personal Finance App Runner
cd /d "%~dp0"
echo ========================================================
echo   Menjalankan Personal Finance App (Backend + Expo Go)
echo ========================================================
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" scripts\run_app.py
) else (
    python scripts\run_app.py
)
pause