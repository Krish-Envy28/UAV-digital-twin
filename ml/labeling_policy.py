"""
Mission Risk Labeling Policy

Defines the deterministic risk labeling logic based strictly on the
FAA/Lycoming operating limits defined in `ml.reference.engine_limits`.
"""

from ml.reference.engine_limits import (
    CHT_CONTINUOUS_MAX_F, CHT_MAX_ABSOLUTE_F,
    OIL_PRESSURE_NORMAL_MIN_PSI, OIL_PRESSURE_NORMAL_MAX_PSI,
    MAX_CONTINUOUS_LOAD_FRACTION, RATED_HP, TBO_HOURS,
)

def thermal_margin(predicted_cht_f: float) -> float:
    """Fraction of remaining temperature buffer before absolute maximum."""
    return (CHT_CONTINUOUS_MAX_F - predicted_cht_f) / (CHT_MAX_ABSOLUTE_F - CHT_CONTINUOUS_MAX_F)

def oil_pressure_ok(predicted_oil_psi: float) -> bool:
    """True if oil pressure is within normal continuous operating range."""
    return OIL_PRESSURE_NORMAL_MIN_PSI <= predicted_oil_psi <= OIL_PRESSURE_NORMAL_MAX_PSI

def load_margin(requested_load_hp: float) -> float:
    """Fraction of remaining continuous load buffer before exceeding recommended limits."""
    safe_continuous_hp = MAX_CONTINUOUS_LOAD_FRACTION * RATED_HP
    return (safe_continuous_hp - requested_load_hp) / safe_continuous_hp

def tbo_consumption(engine_hours_used: float) -> float:
    """Fraction of the published 1800-hour Time Between Overhauls consumed."""
    return engine_hours_used / TBO_HOURS

def label_mission_risk(row: dict) -> int:
    """
    Combines mission parameters and engine state into a risk label.
    Output mapping:
        0 = SAFE
        1 = MODERATE
        2 = HIGH
        3 = CRITICAL
    """
    health_index = row['health_index']
    rul_hours = row['rul_hours']
    degradation_rate = row.get('degradation_rate', 0.0) # Assume 0 if not present
    mission_duration_hours = row['mission_duration'] / 60.0
    engine_load_pct = row['engine_load'] / 100.0
    
    # We approximate expected CHT and Oil Pressure from deviations 
    # to evaluate them against real limits.
    # We will assume a baseline CHT of ~380F and oil pressure of ~75 PSI for healthy states
    # based on typical IO-540 normal ops, plus the deviation.
    predicted_cht_f = 380.0 + (row.get('cht_deviation', 0.0) * 1.8) # convert C to F for the limits
    predicted_oil_psi = 75.0 + row.get('oil_pressure_deviation', 0.0)
    requested_load_hp = engine_load_pct * RATED_HP
    
    t_margin = thermal_margin(predicted_cht_f)
    oil_ok = oil_pressure_ok(predicted_oil_psi)
    l_margin = load_margin(requested_load_hp)
    
    # If RUL cannot support mission, or oil pressure fails, it's critical
    if rul_hours < (mission_duration_hours * 1.2):
        return 3 # CRITICAL
        
    if not oil_ok:
        return 3 # CRITICAL
        
    if health_index < 50.0:
        return 2 # HIGH
        
    if t_margin < 0.0:
        return 2 # HIGH
        
    if health_index < 75.0 or degradation_rate > 0.05:
        if l_margin < 0.0: 
            return 2 # HIGH
        return 1 # MODERATE
        
    if l_margin < -0.1: # Pushing hard (> 75% load) even if healthy
        return 1 # MODERATE
        
    return 0 # SAFE
