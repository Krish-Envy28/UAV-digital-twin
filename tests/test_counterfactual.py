import pytest
from ml.counterfactual import evaluate_mission_scenario

def test_mission_conditioning():
    """Same health state, higher load/duration -> higher risk"""
    engine_state = {
        "health_index": 80.0,
        "degradation_rate": 0.01,
        "rul_hours": 3.0, # 180 mins
        "confidence": 0.9
    }
    
    # Low load mission
    low_risk = evaluate_mission_scenario(engine_state, {
        "duration_minutes": 60,
        "altitude_m": 500,
        "load_pct": 50
    })
    
    # High load mission pushing past limits
    high_risk = evaluate_mission_scenario(engine_state, {
        "duration_minutes": 180,
        "altitude_m": 5000, # Increases effective load
        "load_pct": 100
    })
    
    assert low_risk["risk_score"] < high_risk["risk_score"]
    assert low_risk["risk_level"] in ["LOW", "MODERATE"]
    assert high_risk["risk_level"] == "HIGH"
    
def test_trajectory_awareness():
    """Same mission and health index, but worse degradation rate -> higher risk"""
    mission_params = {
        "duration_minutes": 120,
        "altitude_m": 1000,
        "load_pct": 70
    }
    
    base_state = {
        "health_index": 78.0,
        "rul_hours": 4.0,
        "confidence": 0.9
    }
    
    stable_state = {**base_state, "degradation_rate": 0.01}
    worsening_state = {**base_state, "degradation_rate": 0.06}
    
    stable_risk = evaluate_mission_scenario(stable_state, mission_params)
    worsening_risk = evaluate_mission_scenario(worsening_state, mission_params)
    
    assert worsening_risk["risk_score"] > stable_risk["risk_score"]
    assert "Rapidly worsening degradation rate" in worsening_risk["reason"]

def test_reasoning_string():
    """Ensure reason string is populated correctly based on constraints broken"""
    engine_state = {
        "health_index": 95.0,
        "degradation_rate": 0.0,
        "rul_hours": 1.0, # 60 mins
        "confidence": 0.9
    }
    
    # Mission duration exceeds RUL
    mission_params = {
        "duration_minutes": 120,
        "altitude_m": 0,
        "load_pct": 100
    }
    
    result = evaluate_mission_scenario(engine_state, mission_params)
    assert result["risk_level"] == "HIGH"
    assert "exceeds remaining useful life" in result["reason"]
    assert "exceeds continuous service limits" in result["reason"] # Because load is 100%
