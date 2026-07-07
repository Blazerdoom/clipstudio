@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ClipStudio] Python was not found.
  echo Install it from https://python.org and tick "Add Python to PATH", then run this again.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ClipStudio] Creating virtual environment ^(first run only^)...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo [ClipStudio] Installing / updating dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || (echo [ClipStudio] Dependency install failed. & pause & exit /b 1)

echo [ClipStudio] Checking your environment...
python doctor.py

echo.
echo [ClipStudio] Starting... your browser will open at http://127.0.0.1:8790
start "" "http://127.0.0.1:8790"
python -m app.main

pause
