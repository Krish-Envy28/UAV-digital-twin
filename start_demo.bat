@echo off
cd /d "%~dp0"
echo ==================================================
echo       UAV Digital Twin - Launching Demo...
echo ==================================================

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo.
    echo [!] Virtual environment not found. Creating one now...
    python -m venv .venv
    echo [!] Installing requirements...
    .venv\Scripts\pip.exe install -r requirements.txt
)

echo.
echo [1] Starting Backend API Server in the background...
start "UAV Backend Server" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.api:app"

echo.
echo [2] Waiting for server to initialize (10 seconds)...
timeout /t 10 /nobreak > NUL

echo.
echo [3] Opening Dashboard in your default web browser...
start http://127.0.0.1:8000/

echo.
echo [4] Starting Drone Telemetry Simulation...
echo (You will see the data stream below)
echo ==================================================
.venv\Scripts\python.exe demo_stream.py

echo.
echo Demo finished.
pause
