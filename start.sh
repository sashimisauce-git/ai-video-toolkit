#!/usr/bin/env bash
# AI Video Toolkit — one-click launcher (macOS / Linux)
# Double-click (or: bash start.sh). Sets up Python env, installs deps,
# downloads models on first run, opens the web UI in your browser.
set -e
cd "$(dirname "$0")"

echo "=== AI Video Toolkit ==="

# 1. Python check
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not installed."
  echo "Install it from https://www.python.org/downloads/ then re-run."
  exit 1
fi

# 2. ffmpeg check
if ! command -v ffmpeg &>/dev/null; then
  echo "ERROR: ffmpeg is not installed."
  if command -v brew &>/dev/null; then
    echo "Installing via Homebrew..."
    brew install ffmpeg
  else
    echo "Install ffmpeg for your system:"
    echo "  macOS:   brew install ffmpeg"
    echo "  Ubuntu:  sudo apt install ffmpeg"
    exit 1
  fi
fi

# 3. Virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (one time)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 4. Dependencies
echo "Checking Python packages..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 5. Models (first run downloads ~700MB)
python download_models.py

# 6. Launch
echo ""
echo "Opening AI Video Toolkit in your browser..."
python app.py
