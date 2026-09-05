@echo off
echo ==================================================
echo       UAV Digital Twin - Launching Demo...
echo ==================================================

echo.
echo [1] Starting Backend API Server in the background...
start "UAV Backend Server" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.api:app"

echo.
echo [2] Waiting for server to initialize (3 seconds)...
timeout /t 3 /nobreak > NUL

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
