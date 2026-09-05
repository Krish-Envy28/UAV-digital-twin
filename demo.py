"""
Phase 1A — Team Demo Script
=============================

Run this to demonstrate the entire Digital Twin pipeline to your team.
It walks through each module step-by-step with clear explanations.

Usage:
    .venv\Scripts\python.exe demo.py
"""

import json
import time
import sys
from pathlib import Path

# --- Helpers ---
def pause(msg="Press Enter to continue..."):
    input(f"\n  >> {msg}")
    print()

def header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def step(num, title):
    print(f"\n--- Step {num}: {title} ---\n")


# =====================================================================
#  DEMO START
# =====================================================================

header("PHASE 1A DEMO -- UAV Engine Digital Twin")
print("""
  This demo shows 3 things:

  1. What the synthetic engine data looks like
  2. How the Digital Twin predicts "healthy" values
  3. How residuals detect engine degradation

  No slides needed -- this IS the working system.
""")
pause("Press Enter to start the demo...")


# -----------------------------------------------------------------
# STEP 1: Show the synthetic telemetry data
# -----------------------------------------------------------------
step(1, "Synthetic Engine Telemetry Data")

print("  We simulate a UAV piston engine flying a mission.")
print("  Each second, we record 12 sensor values.\n")

# Load and show a few samples from a healthy run
with open("data/healthy_run_01.jsonl") as f:
    healthy_samples = [json.loads(line) for line in f]

print(f"  Healthy run: {len(healthy_samples)} samples (= {len(healthy_samples)} seconds of flight)\n")
print("  First sample (takeoff - engine starting up):")
sample = healthy_samples[0]
for key, val in sample.items():
    print(f"    {key:20s} = {val}")

print(f"\n  Mid-flight sample (cruising at altitude):")
sample = healthy_samples[len(healthy_samples) // 2]
for key, val in sample.items():
    print(f"    {key:20s} = {val}")

print("\n  Notice: RPM, throttle, altitude change between samples")
print("  --> This is a REALISTIC flight, not flat data")

pause()


# -----------------------------------------------------------------
# STEP 2: Show the degradation trajectory
# -----------------------------------------------------------------
step(2, "Engine Degradation Over Time")

print("  Some runs simulate an engine WEARING OUT over time.")
print("  The engine goes through 5 stages:\n")

with open("data/trajectory_run_01.jsonl") as f:
    trajectory_samples = [json.loads(line) for line in f]

# Find one sample per stage
stages_shown = set()
for s in trajectory_samples:
    stage = s["degradation_stage"]
    if stage not in stages_shown:
        stages_shown.add(stage)
        eh = s["engine_hours"]
        egt = s["egt"]
        vib = s["vibration"]
        oil = s["oil_pressure"]
        print(f"    Stage: {stage:30s}  |  Hours: {eh:6.1f}  |  EGT: {egt:6.1f} C  |  Vibration: {vib:.3f} g  |  Oil Press: {oil:5.1f} psi")

print("\n  See how EGT goes UP, vibration goes UP, oil pressure goes DOWN")
print("  --> That's a degrading engine!")

pause()


# -----------------------------------------------------------------
# STEP 3: Digital Twin in action
# -----------------------------------------------------------------
step(3, "Digital Twin -- Predicting 'Healthy' Values")

from ml.digital_twin import DigitalTwin

twin = DigitalTwin.load("ml/artifacts")
print("  Loaded trained Digital Twin model (6 XGBoost regressors)\n")

# Pick a sample from the trajectory
test_sample = trajectory_samples[len(trajectory_samples) // 2]  # mid-trajectory
print(f"  Test sample from trajectory (stage: {test_sample['degradation_stage']}, hours: {test_sample['engine_hours']:.1f})")
print(f"  Operating conditions:")
print(f"    RPM:          {test_sample['rpm']}")
print(f"    Throttle:     {test_sample['throttle']}%")
print(f"    Altitude:     {test_sample['altitude']} ft")
print(f"    MAP:          {test_sample['map']} kPa")
print(f"    Ambient Temp: {test_sample['ambient_temp']} C\n")

expected = twin.predict(test_sample)

print(f"  What the twin predicts (what a HEALTHY engine would show):")
print(f"  vs what the ACTUAL degraded engine shows:\n")
print(f"    {'Sensor':20s} {'Actual':>10s} {'Expected':>10s} {'Difference':>12s}")
print(f"    {'-'*20} {'-'*10} {'-'*10} {'-'*12}")

for sensor in expected:
    actual_val = test_sample[sensor]
    expected_val = expected[sensor]
    diff = actual_val - expected_val
    flag = " <-- DEGRADED!" if abs(diff) > 5 else ""
    print(f"    {sensor:20s} {actual_val:10.2f} {expected_val:10.2f} {diff:+12.2f}{flag}")

print("\n  The DIFFERENCE between actual and expected = RESIDUAL")
print("  Big residual = something is wrong with the engine")

pause()


# -----------------------------------------------------------------
# STEP 4: Residual Engine
# -----------------------------------------------------------------
step(4, "Residual Engine -- Detecting Problems")

from backend.residual import ResidualEngine

engine = ResidualEngine.from_file("ml/artifacts/std_healthy.json")

# Show residuals for healthy vs degraded
print("  Let's compare a HEALTHY sample vs a DEGRADED sample:\n")

# Healthy sample
h_sample = healthy_samples[len(healthy_samples) // 2]
h_expected = twin.predict(h_sample)
h_actual = {k: h_sample[k] for k in h_expected}
h_result = engine.compute(h_actual, h_expected)

# Degraded sample (late in trajectory)
d_sample = trajectory_samples[-50]  # near the end = critical
d_expected = twin.predict(d_sample)
d_actual = {k: d_sample[k] for k in d_expected}
d_result = engine.compute(d_actual, d_expected)

print(f"    {'Sensor':16s} | {'HEALTHY z-score':>16s} | {'DEGRADED z-score':>17s} | Interpretation")
print(f"    {'-'*16}-+-{'-'*16}-+-{'-'*17}-+-{'-'*20}")

for sensor in h_result["residual_z"]:
    hz = h_result["residual_z"][sensor]
    dz = d_result["residual_z"][sensor]

    if abs(dz) < 3:
        interp = "Normal"
    elif abs(dz) < 10:
        interp = "WARNING"
    else:
        interp = "CRITICAL!"

    print(f"    {sensor:16s} | {hz:+16.2f} | {dz:+17.2f} | {interp}")

print("""
  z-score meaning:
    |z| < 3   = Normal (within healthy noise)
    |z| 3-10  = WARNING (something is off)
    |z| > 10  = CRITICAL (clear fault/degradation)

  The healthy sample has z-scores near 0 (all normal).
  The degraded sample has z-scores >> 3 (engine is failing!)
""")

pause()


# -----------------------------------------------------------------
# STEP 5: Show the acceptance plot
# -----------------------------------------------------------------
step(5, "Visual Proof -- The Acceptance Plot")

plot_path = Path("tests/acceptance_plot.png").resolve()
if plot_path.exists():
    print(f"  The acceptance plot is saved at:")
    print(f"    {plot_path}\n")
    print("  Open it to see:")
    print("    - Left column:  Actual (red) vs Expected (blue) for 3 sensors")
    print("    - Right column: Z-score residuals over time")
    print("    - Background color = degradation stage (green=healthy, red=bad)")
    print("\n  Key takeaway: Blue and red lines OVERLAP in healthy region,")
    print("  then DIVERGE as the engine degrades. Z-scores spike from 0 to 20+.")

    # Try to open the plot
    try:
        import os
        os.startfile(str(plot_path))
        print("\n  [Opening the plot now...]")
    except Exception:
        print(f"\n  [Open this file manually: {plot_path}]")
else:
    print("  Plot not found. Run the acceptance test first:")
    print("    .venv\\Scripts\\python.exe tests/test_acceptance.py")

pause()


# -----------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------
header("DEMO COMPLETE")
print("""
  What we just showed:

  1. SYNTHETIC DATA  -- Realistic UAV engine flights with degradation
  2. DIGITAL TWIN    -- ML model that knows what "healthy" looks like
  3. RESIDUALS       -- The difference between actual and healthy
                        Small = OK,  Large = Problem

  This is Phase 1A. Next (Phase 1B) we use these residuals to:
    - Detect anomalies automatically
    - Classify fault types
    - Estimate remaining useful life (RUL)

  All code is in:
    simulation/   -- data generator
    ml/           -- digital twin model
    backend/      -- residual calculator
    tests/        -- tests + acceptance plot
""")

print("  Commands your team can run:\n")
print("    # Run all tests (should show 21/21 passing):")
print("    .venv\\Scripts\\python.exe -m pytest tests/ -v\n")
print("    # Regenerate the acceptance plot:")
print("    .venv\\Scripts\\python.exe tests/test_acceptance.py\n")
print("    # Regenerate synthetic data:")
print("    .venv\\Scripts\\python.exe -m simulation.telemetry_generator\n")
print("    # Retrain the model:")
print("    .venv\\Scripts\\python.exe -m ml.digital_twin\n")
