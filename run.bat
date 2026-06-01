@echo off
SETLOCAL EnableDelayedExpansion
title PerfBlueprint Launcher

echo ====================================================
echo             PerfBlueprint Bootstrapper              
echo ====================================================

:: Step 1: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please download and install Python 3.9 or higher from https://www.python.org/
    echo *IMPORTANT*: Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Steps 2 & 3: Fast-track check for 2nd run onwards
if exist .venv\.setup_done (
    echo [INFO] Environment verified. Launching application...
    goto :run_app
)

echo [INFO] Setting up isolated Python virtual environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [INFO] Activating environment and updating package managers...
call .venv\Scripts\activate
python -m pip install --upgrade pip

echo [INFO] Installing required dependencies...
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not detected. Installing core runtime packages...
    pip install streamlit requests python-dotenv
)

if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

:: Create the verification marker file
echo true > .venv\.setup_done
echo [SUCCESS] Initial optimization and configuration complete!
echo.

:run_app
if not defined VIRTUAL_ENV (
    call .venv\Scripts\activate
)
echo [INFO] Starting Streamlit UI Engine...
streamlit run app.py
pause