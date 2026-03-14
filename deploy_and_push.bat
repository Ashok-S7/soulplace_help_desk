@echo off
REM In PowerShell run as:  .\deploy_and_push.bat
echo ========================================
echo  Soulplace Help Desk - Deploy to Vercel
echo ========================================
echo.

cd /d "%~dp0"

echo Adding all changes...
git add -A

echo.
echo Committing...
git commit -m "Update: deploy latest changes" 2>nul
if errorlevel 1 (
    echo No changes to commit, or commit failed.
    echo If you see "nothing to commit", your code is already up to date.
) else (
    echo Pushing to GitHub...
    git push origin main
    if errorlevel 1 (
        echo.
        echo PUSH FAILED. You may need to:
        echo 1. Log in to GitHub: run "git push origin main" in PowerShell and enter your credentials.
        echo 2. Use a Personal Access Token as password: GitHub - Settings - Developer settings - Tokens.
    ) else (
        echo.
        echo Done. Wait 1-2 min then open: https://soulplace-help-desk.vercel.app/soulplace/login
    )
)

echo.
pause
