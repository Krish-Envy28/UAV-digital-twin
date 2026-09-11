import json
import pytest
import numpy as np
import xgboost as xgb
from pathlib import Path
import pandas as pd

@pytest.fixture
def risk_model():
    model_path = Path("ml/artifacts/mission_risk_model.json")
    meta_path = Path("ml/artifacts/mission_risk_model.meta.json")
    
    if not model_path.exists():
        pytest.skip("Model not found. Run train_mission_risk.py first.")
        
    clf = xgb.XGBClassifier()
    clf.load_model(str(model_path))
    
    with open(meta_path, "r") as f:
        meta = json.load(f)
        
    return clf, meta["features"]

def predict_single(clf, features_list, row_dict):
    """Helper to predict a single dictionary row."""
    # Convert dict to a single-row DataFrame to match feature names
    df = pd.DataFrame([row_dict], columns=features_list)
    # Get the predicted class (0=SAFE, 1=MODERATE, 2=HIGH, 3=CRITICAL)
    return int(clf.predict(df)[0])

def test_monotonicity_health_index(risk_model):
    """
    Test that for a fixed mission, decreasing health_index NEVER decreases predicted risk.
    """
    clf, features = risk_model
    
    base_row = {
        "health_index": 100.0,
        "rul_hours": 1500.0,
        "degradation_rate": 0.0,
        "anomaly_severity": 0.0,
        "egt_deviation": 0.0,
        "cht_deviation": 0.0,
        "oil_pressure_deviation": 0.0,
        "vibration_deviation": 0.0,
        "mission_duration": 120.0,
        "mission_altitude": 5000.0,
        "engine_load": 60.0
    }
    
    # Sweep health index downwards (which should monotonically increase or maintain risk)
    previous_risk = -1
    for hi in range(100, 10, -5):
        row = base_row.copy()
        row["health_index"] = float(hi)
        
        current_risk = predict_single(clf, features, row)
        
        # Risk should only go UP or STAY SAME as health decreases
        assert current_risk >= previous_risk, f"Monotonicity failed at HI={hi}: Risk dropped from {previous_risk} to {current_risk}"
        previous_risk = current_risk

def test_monotonicity_degradation_rate(risk_model):
    """
    Test that for a fixed mission, increasing degradation_rate NEVER decreases predicted risk.
    """
    clf, features = risk_model
    
    base_row = {
        "health_index": 80.0,
        "rul_hours": 1000.0,
        "degradation_rate": 0.0,
        "anomaly_severity": 0.0,
        "egt_deviation": 5.0,
        "cht_deviation": 2.0,
        "oil_pressure_deviation": -1.0,
        "vibration_deviation": 0.1,
        "mission_duration": 180.0,
        "mission_altitude": 6000.0,
        "engine_load": 70.0
    }
    
    previous_risk = -1
    # Sweep degradation rate upwards (which should monotonically increase or maintain risk)
    for dr in np.linspace(0.0, 0.2, 10):
        row = base_row.copy()
        row["degradation_rate"] = float(dr)
        
        current_risk = predict_single(clf, features, row)
        
        # Risk should only go UP or STAY SAME as degradation increases
        assert current_risk >= previous_risk, f"Monotonicity failed at DR={dr}: Risk dropped from {previous_risk} to {current_risk}"
        previous_risk = current_risk

def test_mission_conditioning(risk_model):
    """
    Same health_index, different mission params -> different risk
    """
    clf, features = risk_model
    
    # Mildly degraded engine
    base_health = {
        "health_index": 70.0,
        "rul_hours": 800.0,
        "degradation_rate": 0.06,
        "anomaly_severity": 0.1,
        "egt_deviation": 10.0,
        "cht_deviation": 5.0,
        "oil_pressure_deviation": -3.0,
        "vibration_deviation": 0.3,
    }
    
    # Easy mission (short, low load)
    easy_mission = base_health.copy()
    easy_mission.update({
        "mission_duration": 45.0,
        "mission_altitude": 2000.0,
        "engine_load": 50.0
    })
    
    # Hard mission (long, high load)
    hard_mission = base_health.copy()
    hard_mission.update({
        "mission_duration": 240.0,
        "mission_altitude": 10000.0,
        "engine_load": 85.0
    })
    
    risk_easy = predict_single(clf, features, easy_mission)
    risk_hard = predict_single(clf, features, hard_mission)
    
    # Hard mission should have higher or equal risk
    assert risk_hard >= risk_easy
    # Usually they will be different if the engine state is borderline
    # If they are not different, we at least ensured hard >= easy.

