@echo off
REM AI Video Toolkit — one-click launcher (Windows)
REM Double-click start.bat. Sets up Python env, installs deps,
REM downloads models on first run, opens the web UI in your browser.
cd /d "%~dp0"

echo === AI Video Toolkit ===

REM 1. Python check
python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3 is not installed.
  echo Install it from https://www.python.org/downloads/
  echo IMPORTANT: tick "Add python.exe to PATH" during install.
  pause
  exit /b 1
)

REM 2. ffmpeg check
ffmpeg -version >nul 2>&1
if errorlevel 1 (
  echo ERROR: ffmpeg is not installed.
  echo Install it via: winget install ffmpeg
  echo Or download from https://www.gyan.dev/ffmpeg/builds/
  pause
  exit /b 1
)

REM 3. Virtual environment
if not exist ".venv" (
  echo Creating virtual environment (one time)...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

REM 4. Dependencies
echo Checking Python packages...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

REM 5. Models (first run downloads ~700MB)
python download_models.py

REM 6. Launch
echo.
echo Opening AI Video Toolkit in your browser...
python app.py
pause
