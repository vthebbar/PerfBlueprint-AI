#!/bin/bash

echo "===================================================="
echo "            PerfBlueprint Bootstrapper              "
echo "===================================================="

# Step 1: Check for Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python is not installed on this system."
    echo "Please install Python 3.9 or higher via Homebrew (brew install python) or from https://www.python.org/"
    exit 1
fi

# Steps 2 & 3: Fast-track check for 2nd run onwards
if [ -f ".venv/.setup_done" ]; then
    echo "[INFO] Environment verified. Launching application..."
    source .venv/bin/activate
    streamlit run app.py
    exit 0
fi

echo "[INFO] Setting up isolated Python virtual environment..."
$PYTHON_CMD -m venv .venv
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to create virtual environment."
    exit 1
fi

echo "[INFO] Activating environment and updating package managers..."
source .venv/bin/activate
python -m pip install --upgrade pip

echo [INFO] Installing required dependencies...
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "[WARNING] requirements.txt not detected. Installing core runtime packages..."
    pip install streamlit requests python-dotenv
fi

if [ $? -ne 0 ]; then
    echo "[ERROR] Dependency installation failed."
    exit 1
fi

# Create the verification marker file
touch .venv/.setup_done
echo "[SUCCESS] Initial optimization and configuration complete!"
echo ""

echo "[INFO] Starting Streamlit UI Engine..."
streamlit run app.py