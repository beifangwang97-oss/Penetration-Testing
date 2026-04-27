@echo off
cd /d "%~dp0"
echo Starting evaluation console on http://localhost:8084
"D:\anaconda3\python.exe" -u app.py
if errorlevel 1 (
    echo.
    echo Server exited with an error.
    pause
)
