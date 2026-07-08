#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ---- ClipStudio, reachable from other devices on your Wi-Fi / LAN ----
# Same as run.sh, but binds to all interfaces so phones/other machines on the
# same network can connect. You may need to allow port 8790 in your firewall.

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ClipStudio] python3 not found. Install Python 3.10+ and try again."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[ClipStudio] Creating virtual environment (first run only)..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[ClipStudio] Installing / updating dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

export CLIPSTUDIO_HOST=0.0.0.0

echo ""
echo "[ClipStudio] Starting on your network — other devices use the http://<LAN-IP>:8790 address printed below."
python -m app.main
