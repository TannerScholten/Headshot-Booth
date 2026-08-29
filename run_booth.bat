@echo off
title Headshot Booth & Delivery System
cd /d "%~dp0"

echo =========================================================
echo    HEADSHOT BOOTH & DELIVERY SYSTEM - 1-CLICK RUNNER
echo =========================================================
echo.
echo Starting local Booth server at http://localhost:8000 ...
echo Press Ctrl+C at any time to stop.
echo.

start "" http://localhost:8000
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

pause
