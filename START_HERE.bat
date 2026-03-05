@echo off
title Soulplace Help Desk
cd /d "%~dp0"

echo.
echo ============================================
echo   SOULPLACE HELP DESK - START
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found. Install Python from python.org
    echo Then run this file again.
    pause
    exit /b 1
)

echo [1/3] Installing packages...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo       Done.
echo.

echo [2/3] Starting server...
echo.
echo   WHEN YOU SEE "Running on" BELOW, OPEN IN BROWSER:
echo.
echo   PC:    http://127.0.0.1:5000/soulplace/login
echo.
echo   PHONE: Use the "On your phone" URL shown below
echo          (phone must be on same Wi-Fi as this PC)
echo.
echo ============================================
echo.

start "" http://127.0.0.1:5000/soulplace/login

python app.py

pause
