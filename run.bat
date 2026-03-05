@echo off
cd /d "%~dp0"
echo Installing dependencies...
pip install -r requirements.txt -q
echo.
echo Starting Soulplace Help Desk...
echo   On PC:    http://127.0.0.1:5000/soulplace/login
echo   On phone: use the URL shown below (same Wi-Fi)
echo.
start http://127.0.0.1:5000/soulplace/login
python app.py
