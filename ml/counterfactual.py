import math
from typing import Dict, Any

from ml.reference.engine_limits import MAX_CONTINUOUS_LOAD_FRACTION

def evaluate_mission_scenario(engine_state: Dict[str, Any], mission_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates mission risk deterministically based on Phase 1B outputs and mission parameters.
    
    engine_state expected keys:
        - health_index (0-100)
        - degradation_stage (string)
        - degradation_rate (float)
        - rul_hours (float, we convert to minutes)
        - confidence (0-1)
        
    mission_params expected keys:
        - duration_minutes (float)
        - altitude_m (float)
        - load_pct (float, 0-100)
    """
    # Extract inputs
    health_index = float(engine_state.get('health_index', 100))
    degradation_rate = float(engine_state.get('degradation_rate', 0.0))
    rul_minutes = float(engine_state.get('rul_hours', 0.0)) * 60
    confidence = float(engine_state.get('confidence', 1.0))
    
    duration_minutes = float(mission_params.get('duration_minutes', 120))
    altitude_m = float(mission_params.get('altitude_m', 500))
    load_pct = float(mission_params.get('load_pct', 100))
    
    # 1. Effective Load Calculation
    # Higher altitudes increase engine strain due to thinner air (approximate multiplier)
    altitude_penalty = 1.0 + (altitude_m / 10000.0) # e.g. 5000m adds 50% strain
    base_load_fraction = load_pct / 100.0
    effective_load_factor = base_load_fraction * altitude_penalty
    
    # 2. Operating Margin Calculation
    # How much of predicted RUL does this mission consume?
    consumed_rul_minutes = duration_minutes * effective_load_factor
    operating_margin = rul_minutes - consumed_rul_minutes
    
    # 3. Dynamic Penalties
    risk_score = 0.0
    reasons = []
    
    # Margin penalty
    if operating_margin < 0:
        risk_score += 100
        reasons.append("Mission duration exceeds remaining useful life (RUL) under these load conditions.")
    elif operating_margin < (60 * effective_load_factor): # Less than 1 hour buffer
        risk_score += 40
        reasons.append("Narrow operating margin. Mission consumes almost all remaining RUL.")
    
    # Degradation Rate Penalty (independent of absolute health)
    if degradation_rate > 0.05:
        risk_score += 50
        reasons.append("Rapidly worsening degradation rate observed.")
    elif degradation_rate > 0.02:
        risk_score += 20
        reasons.append("Elevated degradation rate observed.")
        
    # Health Index Penalty
    if health_index < 50:
        risk_score += 30
        reasons.append("Engine health index is critically low.")
    elif health_index < 75:
        risk_score += 10
        reasons.append("Engine health is suboptimal.")
        
    # Load Limit Penalty (Lycoming constraint)
    if base_load_fraction > MAX_CONTINUOUS_LOAD_FRACTION:
        duration_penalty = max(0, duration_minutes - 60) * 0.5 # Penalty for extended high load
        risk_score += min(30, duration_penalty)
        if duration_penalty > 0:
            reasons.append(f"Mission load ({load_pct}%) exceeds continuous service limits for extended duration.")
            
    # Confidence Penalty
    if confidence < 0.7:
        risk_score += (0.7 - confidence) * 100
        reasons.append("Low confidence in telemetry predictions requires a wider safety margin.")
        
    # Final Score and Categorization
    risk_score = min(100.0, max(0.0, risk_score))
    
    if risk_score >= 70:
        risk_level = "HIGH"
        if operating_margin < 0 or health_index < 30:
            recommendation = "RETURN_TO_BASE"
        else:
            recommendation = "MAINTENANCE_REQUIRED"
    elif risk_score >= 30:
        risk_level = "MODERATE"
        recommendation = "MODIFY"
    else:
        risk_level = "LOW"
        recommendation = "CONTINUE"
        
    if not reasons:
        reasons.append("Mission parameters are well within safe operating margins and engine health is stable.")
        
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "operating_margin": operating_margin,
        "recommendation": recommendation,
        "reason": " ".join(reasons)
    }
