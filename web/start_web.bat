@echo off
title Discord 7K Badge Farmer - 12 Slots Web Dashboard
cd /d "%~dp0"

echo ===================================================
echo     Discord 7K Badge Farmer - 12 Slots Dashboard
echo ===================================================
echo.
echo Starting Web Server on http://localhost:5000 ...
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python 3.10+ was not found in your PATH!
        echo Please install Python from https://www.python.org/
        pause
        exit /b 1
    ) else (
        set PYCMD=py
    )
) else (
    set PYCMD=python
)

:: Start default browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Start the Python Web Server in the web folder
%PYCMD% server.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server stopped with exit code: %errorlevel%
    pause
)
