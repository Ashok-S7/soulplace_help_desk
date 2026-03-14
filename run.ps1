# Soulplace Help Desk - Run in PowerShell
Set-Location $PSScriptRoot

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: pip install failed. Check Python and requirements.txt." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting Soulplace Help Desk..." -ForegroundColor Green
Write-Host "  When you see 'Running on http://...', open in browser:" -ForegroundColor Yellow
Write-Host "  http://127.0.0.1:5000/soulplace/login" -ForegroundColor Cyan
Write-Host "  On phone (same Wi-Fi): use your PC IP, e.g. http://192.168.x.x:5000/soulplace/login" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

python app.py
