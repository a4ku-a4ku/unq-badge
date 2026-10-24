@echo off
title Discord Badge Spoofer
cd /d "%~dp0"

echo ===================================================
echo             Discord Badge Spoofer
echo ===================================================
echo.

where python >nul 2>&1
if %errorlevel% equ 0 (
    python spoofer.py
    goto end
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    py spoofer.py
    goto end
)

echo [ERROR] Python was not found in your PATH!
echo Please install Python 3.10+ from https://www.python.org/ or add it to PATH.
echo.

:end
if %errorlevel% neq 0 (
    echo.
    echo Script ended with an error code: %errorlevel%
)
echo.
pause
