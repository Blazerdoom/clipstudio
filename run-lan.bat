@echo off
setlocal
cd /d "%~dp0"

REM ---- ClipStudio, reachable from other devices on your Wi-Fi / LAN ----
REM Same as run.bat, but binds to all network interfaces and opens the
REM firewall for port 8790 so phones/other PCs on the same network can connect.

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

REM Open the Windows Firewall for the app port (needs admin; skipped otherwise).
echo [ClipStudio] Opening firewall for port 8790 ^(may ask for admin^)...
netsh advfirewall firewall show rule name="ClipStudio 8790" >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process netsh -Verb RunAs -ArgumentList 'advfirewall firewall add rule name=\"ClipStudio 8790\" dir=in action=allow protocol=TCP localport=8790' -WindowStyle Hidden" 2>nul
)

set CLIPSTUDIO_HOST=0.0.0.0

echo.
echo [ClipStudio] Starting on your network. This PC: http://127.0.0.1:8790
echo [ClipStudio] Other devices: use the "http://192.168.x.x:8790" address printed below.
start "" "http://127.0.0.1:8790"
python -m app.main

pause
