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
import xgboost as xgb
import json
import pandas as pd
from backend.residual import ResidualEngine
from ml.phm_core import PHMCore
from backend.event_manager import event_manager
from ml.counterfactual import evaluate_mission_scenario


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

mission_model_path = Path(__file__).parent.parent / "ml" / "artifacts" / "mission_risk_model.json"
mission_meta_path = Path(__file__).parent.parent / "ml" / "artifacts" / "mission_risk_model.meta.json"

mission_risk_model = None
mission_features = []
mission_importances = {}

if mission_model_path.exists():
    mission_risk_model = xgb.XGBClassifier()
    mission_risk_model.load_model(str(mission_model_path))
    with open(mission_meta_path, "r") as f:
        meta = json.load(f)
        mission_features = meta["features"]
        mission_importances = meta["importances"]

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

# ---- Mission Risk AI Endpoints ----

class MissionParams(BaseModel):
    duration_minutes: float
    target_altitude: float
    engine_load_pct: float

class MissionAnalyzeRequest(BaseModel):
    engine_state: dict
    mission: MissionParams

def build_mission_feature_dict(engine_state, mission):
    # Extract features safely
    health_idx = engine_state.get("health_index", 100.0)
    return {
        "health_index": health_idx,
        "rul_hours": engine_state.get("rul_hours", 1800.0),
        "degradation_rate": engine_state.get("degradation_rate", 0.0),
        "anomaly_severity": engine_state.get("anomaly_score", 0.0) if health_idx < 90 else 0.0,
        "egt_deviation": engine_state.get("residual_z", {}).get("egt", 0.0) * 15.0, # roughly un-standardizing
        "cht_deviation": engine_state.get("residual_z", {}).get("cht", 0.0) * 10.0,
        "oil_pressure_deviation": engine_state.get("residual_z", {}).get("oil_pressure", 0.0) * 5.0,
        "vibration_deviation": engine_state.get("residual_z", {}).get("vibration", 0.0) * 0.5,
        "mission_duration": mission.duration_minutes,
        "mission_altitude": mission.target_altitude,
        "engine_load": mission.engine_load_pct
    }

@app.post("/api/mission/analyze")
def analyze_mission(req: MissionAnalyzeRequest):
    if not mission_risk_model:
        return {"error": "Mission model not trained"}
        
    f_dict = build_mission_feature_dict(req.engine_state, req.mission)
    df = pd.DataFrame([f_dict], columns=mission_features)
    
    pred_idx = int(mission_risk_model.predict(df)[0])
    probs = mission_risk_model.predict_proba(df)[0]
    
    labels = ["SAFE", "MODERATE", "HIGH", "CRITICAL"]
    label = labels[pred_idx]
    
    # Simple top drivers logic from global importances
    top_drivers = sorted(mission_importances.items(), key=lambda x: x[1], reverse=True)[:3]
    drivers_out = [{"feature": k, "importance": v} for k, v in top_drivers]
    
    return {
        "risk": label,
        "risk_score": float(pred_idx) / 3.0, # Normalize to 0-1
        "confidence": float(probs[pred_idx]),
        "top_drivers": drivers_out
    }

class MissionWhatIfRequest(BaseModel):
    engine_state: dict
    original_mission: MissionParams
    alternatives: List[MissionParams]

@app.post("/api/mission/what-if")
def what_if_mission(req: MissionWhatIfRequest):
    scenarios = []
    
    # Process original
    orig_params = {
        "duration_minutes": req.original_mission.duration_minutes,
        "altitude_m": req.original_mission.target_altitude,
        "load_pct": req.original_mission.engine_load_pct
    }
    
    orig_result = evaluate_mission_scenario(req.engine_state, orig_params)
    
    scenarios.append({
        "label": "Original",
        "params": orig_params,
        "result": orig_result
    })
    
    best_alt_label = None
    best_score = orig_result["risk_score"]
    
    for i, alt in enumerate(req.alternatives):
        alt_params = {
            "duration_minutes": alt.duration_minutes,
            "altitude_m": alt.target_altitude,
            "load_pct": alt.engine_load_pct
        }
        
        alt_result = evaluate_mission_scenario(req.engine_state, alt_params)
        alt_name = f"Alternative {i+1}"
        
        scenarios.append({
            "label": alt_name,
            "params": alt_params,
            "result": alt_result
        })
        
        if alt_result["risk_score"] < best_score:
            best_score = alt_result["risk_score"]
            best_alt_label = alt_name
            
    return {
        "scenarios": scenarios,
        "best_alternative": best_alt_label
    }

@app.post("/api/mission/recommend")
def recommend_mission(req: dict):
    # Rule-based logic separated from the ML model
    risk = req.get("risk", "SAFE")
    load = req.get("mission", {}).get("engine_load_pct", 100)
    
    if risk == "CRITICAL":
        return {
            "action": "ABORT / RETURN TO BASE",
            "reason": "Risk model indicates critical failure likelihood on this trajectory.",
            "expected_effect": "CRITICAL -> SAFE"
        }
    elif risk == "HIGH":
        if load > 75:
            return {
                "action": "REDUCE_LOAD",
                "reason": "Engine load is high, increasing degradation risk. Reduce to 65%.",
                "expected_effect": "HIGH -> MODERATE"
            }
        else:
            return {
                "action": "SHORTEN_MISSION",
                "reason": "Mission duration exceeds safe RUL buffer. Consider RTB sooner.",
                "expected_effect": "HIGH -> MODERATE"
            }
    elif risk == "MODERATE":
        return {
            "action": "MONITOR",
            "reason": "Risk is elevated but within acceptable limits. Maintain steady telemetry.",
            "expected_effect": "MODERATE -> MODERATE"
        }
        
    return {
        "action": "CONTINUE",
        "reason": "Mission profile is safe given current engine health.",
        "expected_effect": "SAFE -> SAFE"
    }

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
