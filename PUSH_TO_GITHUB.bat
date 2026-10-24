@echo off
title A4KU - Push to GitHub
cd /d "%~dp0"
echo ============================================================
echo   Pushing to GitHub: https://github.com/a4ku-a4ku/discord-badge-spoofer
echo ============================================================
echo.
"C:\Users\vive1\AppData\Local\GitHubDesktop\app-3.6.4\resources\app\git\cmd\git.exe" push -u origin main
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Successfully pushed to GitHub!
    echo Opening Render Blueprint deployment...
    start msedge "https://dashboard.render.com/blueprints/new"
) else (
    echo.
    echo [ERROR] Push failed. Make sure you clicked 'Create repository' in Edge first!
)
pause
