from __future__ import annotations

import asyncio
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
from pathlib import Path
# Ensure we can import ml and backend
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.digital_twin import DigitalTwin
from backend.residual import ResidualEngine
from ml.phm_core import PHMCore
from backend.event_manager import event_manager


app = FastAPI(title="UAV Digital Twin - Phase 2 API")

# Allow frontend to call API from any origin (needed for speed toggle)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Global Models ----
print("Loading ML models...")
twin = DigitalTwin.load()
residual_engine = ResidualEngine.from_file()
phm = PHMCore.load()
print("Models loaded successfully.")

# ---- WebSocket Connection Manager ----
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


# ---- Input Schema ----
class TelemetryInput(BaseModel):
    timestamp: float
    engine_hours: float
    rpm: float
    throttle: float
    map: float
    altitude: float
    ambient_temp: float
    egt: float
    cht: float
    oil_pressure: float
    oil_temp: float
    vibration: float
    fuel_flow: float


# ---- API Endpoints ----
@app.post("/api/telemetry")
async def receive_telemetry(data: TelemetryInput):
    """
    Receives raw telemetry from the drone (or simulation script).
    Runs the full PHM pipeline and broadcasts to connected frontends.
    """
    raw_sample = data.model_dump()
    
    # 1. Digital Twin predicts expected healthy values
    expected = twin.predict(raw_sample)
    
    # 2. Residual Engine compares actual vs expected
    res = residual_engine.compute(raw_sample, expected)
    rz = res["residual_z"]
    
    # 3. PHM Core estimates health
    phm_result = phm.predict(rz, data.engine_hours)
    
    # 4. Event Management (Process new anomalies)
    event_manager.process_telemetry(raw_sample, rz, phm_result)
    
    # Combine everything for the dashboard
    broadcast_data = {
        "timestamp": data.timestamp,
        "engine_hours": data.engine_hours,
        "raw": {
            "egt": data.egt,
            "cht": data.cht,
            "oil_pressure": data.oil_pressure,
            "oil_temp": data.oil_temp,
            "vibration": data.vibration,
            "fuel_flow": data.fuel_flow,
            "rpm": data.rpm,
            "altitude": data.altitude,
            "throttle": data.throttle
        },
        "expected": expected,
        "residual_z": rz,
        "phm": phm_result
    }
    
    # Broadcast to web dashboard
    await manager.broadcast(broadcast_data)
    
    return {"status": "processed", "health_index": phm_result["health_index"]}

# Speed state for the demo stream
global_speed_factor = 10

class SpeedRequest(BaseModel):
    speed: int

@app.get("/api/speed")
def get_speed():
    return {"speed": global_speed_factor}

@app.post("/api/speed")
def set_speed(req: SpeedRequest):
    global global_speed_factor
    global_speed_factor = req.speed
    return {"status": "ok", "speed": global_speed_factor}

@app.get("/api/events")
def get_events():
    return {"events": event_manager.get_events()}

@app.get("/api/events/{event_id}")
def get_event(event_id: str):
    evt = event_manager.get_event(event_id)
    if evt:
        return evt
    return {"error": "Event not found"}, 404

from fastapi.responses import FileResponse
@app.get("/api/events/{event_id}/image")
def get_event_image(event_id: str):
    image_path = Path(__file__).parent.parent / "data" / "events" / event_id / "snapshot.svg"
    if image_path.exists():
        return FileResponse(image_path, media_type="image/svg+xml")
    return {"error": "Image not found"}, 404

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Frontend dashboards connect here to receive real-time streams.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We just keep connection alive, frontend only listens
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Serve the frontend UI files from the root
# E.g. http://localhost:8000/ connects to index.html
frontend_dir = Path(__file__).parent.parent / "frontend"
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
