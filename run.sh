#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

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

echo "[ClipStudio] Checking your environment..."
python doctor.py || true

echo ""
echo "[ClipStudio] Starting at http://127.0.0.1:8790"
python -m app.main
