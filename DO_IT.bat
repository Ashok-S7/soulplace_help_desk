@echo off
title Deploy to Vercel - Do it
cd /d "%~dp0"
echo.
echo  Opening Vercel...
start https://vercel.com/new
echo.
echo  IN THE BROWSER (do these 4 steps):
echo.
echo  1. Sign in with Google or GitHub
echo  2. Click "Import" and choose your GitHub repo
echo     (If you don't have a repo yet: go to github.com, New repo,
echo      then upload this folder "soulplace_help_desk")
echo  3. Root Directory: leave as is (or set to soulplace_help_desk if the repo has a parent folder)
echo  4. Click "Deploy"
echo.
echo  When it finishes, your link appears on the page.
echo  Example: https://soulplace-help-desk-xxxxx.vercel.app
echo  Login: add /soulplace/login to that URL
echo.
echo  More help: open CREATE_VERCEL.md in this folder
echo.
pause
