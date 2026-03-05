@echo off
title Create Vercel - Soulplace Help Desk
cd /d "%~dp0"
echo.
echo Opening Vercel to create your deployment...
echo.
echo In the browser:
echo   1. Sign in with GitHub
echo   2. Import your repo (push soulplace_help_desk to GitHub first)
echo   3. Set Root Directory if needed, then Deploy
echo   4. Copy your link when the deploy finishes
echo.
echo Full steps are in: CREATE_VERCEL.md
echo.
start https://vercel.com/new
pause
