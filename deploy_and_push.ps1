# Soulplace Help Desk - Deploy to Vercel (PowerShell)
# Run: Right-click this file -> Run with PowerShell
# Or in PowerShell: cd "c:\mini project\soulplace_help_desk" ; .\deploy_and_push.ps1

Set-Location $PSScriptRoot

Write-Host "========================================"
Write-Host " Soulplace Help Desk - Deploy to Vercel"
Write-Host "========================================"
Write-Host ""

Write-Host "Adding all changes..."
git add -A

Write-Host "Committing..."
git commit -m "Update: deploy latest changes" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "No changes to commit (or commit failed)."
} else {
    Write-Host "Pushing to GitHub..."
    git push origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Done. Wait 1-2 min then open: https://soulplace-help-desk.vercel.app/soulplace/login"
    } else {
        Write-Host "Push failed. Check DEPLOY_STEPS.txt for login/token help."
    }
}

Write-Host ""
Read-Host "Press Enter to close"
