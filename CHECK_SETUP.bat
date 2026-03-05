@echo off
cd /d "%~dp0"
echo Checking Soulplace setup...
echo.

python --version 2>nul
if errorlevel 1 (
    echo [FAIL] Python not installed or not in PATH.
    echo        Install from https://www.python.org/downloads/
    echo        Tick "Add Python to PATH" when installing.
    pause
    exit /b 1
)
echo [OK] Python found.

pip show flask >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing packages...
    pip install -r requirements.txt -q
)
echo [OK] Packages OK.

python -c "from app import app; print('[OK] App loads.')" 2>nul
if errorlevel 1 (
    echo [FAIL] App has an error. Run: python app.py
    pause
    exit /b 1
)

echo.
echo All checks passed. Run START_HERE.bat to start the app.
pause
