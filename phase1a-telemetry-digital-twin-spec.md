# Phase 1A — Telemetry + Digital Twin Specification
### UAV Engine Digital Twin (SIH) — `uav-engine-digital-twin`

Goal for this phase: **Telemetry → Digital Twin → Expected Values → Residuals** works end-to-end, before anything else is built.

---

## 1. Telemetry Schema

| Field | Type | Unit | Role |
|---|---|---|---|
| `timestamp` | ISO 8601 / float (s) | s | sample time |
| `rpm` | float | rev/min | operating state |
| `throttle` | float | % (0–100) | mission demand / input |
| `map` | float | kPa (or inHg) | engine load |
| `altitude` | float | ft | operating environment / input |
| `ambient_temp` | float | °C | input (context) |
| `egt` | float | °C | expected output |
| `cht` | float | °C | expected output |
| `oil_pressure` | float | psi (or kPa) | expected output |
| `oil_temp` | float | °C | expected output |
| `vibration` | float | g (RMS) | expected output |
| `fuel_flow` | float | L/h (or kg/h) | expected output |
| `engine_hours` | float | h | optional, for degradation trajectory |

Split into two groups, since the Digital Twin predicts one group from the other:

- **Twin inputs (operating conditions):** `rpm`, `throttle`, `map`, `altitude`, `ambient_temp`, (optionally `engine_hours` as a slow-drift feature)
- **Twin outputs (predicted "healthy" behaviour):** `egt`, `cht`, `oil_pressure`, `oil_temp`, `vibration`, `fuel_flow`

## 2. Data Types & Format

- Wire/storage format: **JSON Lines** (`.jsonl`) or **Parquet** for batch datasets; JSON objects for the streamed/replayed real-time interface.
- Example single sample:

```json
{
  "timestamp": 1234.5,
  "rpm": 4200,
  "throttle": 62.0,
  "map": 78.3,
  "altitude": 8500,
  "ambient_temp": 12.4,
  "egt": 715.2,
  "cht": 168.9,
  "oil_pressure": 55.1,
  "oil_temp": 91.0,
  "vibration": 0.42,
  "fuel_flow": 11.8,
  "engine_hours": 214.6
}
```

## 3. Sampling Rate

- Source datasets: whatever the historical/synthetic source provides (typically 1 Hz for engine PHM datasets).
- Replay/stream rate for the demo: **1 sample/sec**, configurable multiplier (e.g. 1x, 10x, 60x) so a full mission can be replayed quickly for judges.
- Digital Twin inference: runs on every incoming sample (no batching needed at this scale).

## 4. Digital Twin — Inputs / Outputs

**Input vector `X`** (operating condition, at time `t`, optionally with short history window `t-k..t` for smoothing):
`[rpm, throttle, map, altitude, ambient_temp]`

**Output vector `Ŷ`** (expected healthy sensor values at time `t`):
`[egt_hat, cht_hat, oil_pressure_hat, oil_temp_hat, vibration_hat, fuel_flow_hat]`

**Model choice for MVP:** train one regressor per output (or one multi-output regressor) — e.g. gradient-boosted trees (XGBoost/LightGBM) or a small MLP — fit **only on healthy-region data** so it learns "what normal looks like" for a given operating condition. Avoid an LSTM here initially; a per-timestep conditional regressor is enough to demonstrate the residual concept and is far faster to get working in Day 1.

## 5. Expected-Value Model Requirements

- Must be **condition-aware**: same `egt` value should be judged differently at high load vs low load (this is the whole point vs. static thresholds).
- Must be trained/fit exclusively on data labeled/assumed **healthy** (early engine-hours or explicitly clean subset).
- Should expose a simple `predict(X) -> Ŷ` interface so it's swappable later (e.g. replaced by an LSTM) without touching downstream modules.

## 6. Residual Calculation

```
residual[i] = actual[i] - expected[i]      for each sensor i in twin outputs
```

Additionally compute a **normalized residual** so different units/scales are comparable:

```
z[i] = (actual[i] - expected[i]) / std_healthy[i]
```

where `std_healthy[i]` is the residual standard deviation observed on healthy data for that sensor. This normalized vector `z` is what feeds the AI PHM core in Phase 1B (anomaly/fault/health/RUL).

Output of this module per sample:

```json
{
  "timestamp": 1234.5,
  "actual": {"egt": 715.2, "cht": 168.9, ...},
  "expected": {"egt": 702.1, "cht": 165.3, ...},
  "residual": {"egt": 13.1, "cht": 3.6, ...},
  "residual_z": {"egt": 0.87, "cht": 0.31, ...}
}
```

## 7. Healthy vs Degraded Data Representation

- Each simulated/replayed run is labeled at the run level with a **degradation stage**: `healthy → early_deviation → incipient_degradation → progressive_degradation → critical`.
- Store this as a `degradation_stage` field per sample (or per run, if generated as a monotonic trajectory), used for:
  - Training the Digital Twin only on `healthy` segments.
  - Later training the fault/degradation classifier (Phase 1B) using stage as (part of) the label.
- Synthetic generation approach: start from a healthy baseline signal per sensor, then inject a slow drift/noise-growth function keyed to `engine_hours` (or elapsed mission time) to move through the stages above. Keep this generator isolated in `simulation/` so it's clearly disclosed as synthetic.

## 8. Module / API Boundaries

```
[Telemetry Engine] --sample--> [Digital Twin] --(actual, expected)--> [Residual Engine] --residual/z--> [AI PHM Core]
```

- **Telemetry Engine**: `get_next_sample() -> dict` (replay iterator over historical/synthetic data at configurable rate)
- **Digital Twin**: `predict(sample: dict) -> dict` (returns expected values for the twin-output fields)
- **Residual Engine**: `compute(actual: dict, expected: dict) -> dict` (returns residual + residual_z)
- Each module is a plain Python class/function with a fixed JSON-in/JSON-out contract, callable directly now and exposable over a lightweight API (FastAPI) later for the dashboard — no need to stand up the API layer until Phase 3/4.

---

## Immediate build order (Day 1)

1. `simulation/` — synthetic piston-engine telemetry generator with the 5-stage degradation trajectory.
2. `data/` — healthy-only slice extracted for Digital Twin training.
3. `ml/digital_twin.py` — train the per-sensor regressors on healthy data; expose `predict()`.
4. `backend/residual.py` — residual + normalized residual computation.
5. Quick script/notebook: replay one run end-to-end and plot `actual` vs `expected` vs `residual` for at least `egt` and `oil_pressure` to visually confirm the twin tracks operating-condition changes and residuals spike during the injected degradation stages.

That plot is the proof point for Day 1: **"Telemetry → Digital Twin → Residual works."**

---

## What to tell Antigravity (Day 1 build prompt)

Paste this in as the task brief. It references this spec so the agent has the exact contracts instead of inventing its own.

```
Project: uav-engine-digital-twin
Context: Full spec is in docs/phase1a-telemetry-digital-twin-spec.md — read it first
and follow it exactly. Do not redesign the schema or module boundaries.

Full system architecture (for context — only the first 3 boxes are Day 1 scope):

  MALE UAV / SIMULATED TELEMETRY
              |
              v
  +-------------------------+
  | Telemetry Stream        |
  | RPM / MAP / EGT         |   <-- Day 1: simulation/telemetry_generator.py
  | CHT / Oil / Vib.        |
  +-------------------------+
              |
              v
  +-------------------------+
  | DIGITAL TWIN            |
  | Expected Engine         |   <-- Day 1: ml/digital_twin.py
  | Behaviour Model         |
  +-------------------------+
              |
              v
     Actual - Expected = RESIDUAL   <-- Day 1: backend/residual.py
              |
              v
  +-------------------------+
  | AI PHM CORE             |
  | Anomaly                 |
  | Fault/Degradation       |   <-- Phase 1B, NOT Day 1 — do not build yet
  | Health Index            |
  | RUL + Confidence        |
  +-------------------------+
              |
              v
  +-------------------------+
  | MISSION ANALYZER        |
  | Duration                |
  | Altitude                |   <-- Phase 3, NOT Day 1 — do not build yet
  | Load/Throttle           |
  +-------------------------+
              |
              v
  +-------------------------+
  | MISSION RISK            |
  | + WHAT-IF                |  <-- Phase 3, NOT Day 1 — do not build yet
  +-------------------------+
              |
              v
  Continue / Monitor / Reduce Load / RTB / Maintenance  <-- Phase 3/4, NOT Day 1

Repo layout to create/use:
  simulation/   synthetic telemetry generator
  data/         generated datasets (healthy slice + full runs)
  ml/           digital_twin.py
  backend/      residual.py
  docs/         this spec + any notes
  tests/        unit tests for the three modules below

Build these three modules, in order, each with a fixed JSON-in/JSON-out
contract (no API layer yet — plain Python callables):

1. simulation/telemetry_generator.py
   - Generate synthetic piston-engine telemetry runs matching the schema
     in section 1 of the spec (rpm, throttle, map, altitude, ambient_temp,
     egt, cht, oil_pressure, oil_temp, vibration, fuel_flow, engine_hours).
   - Each run must progress through degradation_stage: healthy ->
     early_deviation -> incipient_degradation -> progressive_degradation ->
     critical, driven by engine_hours, per section 7.
   - Output JSONL, one sample per line, per the example in section 2.
   - Generate at least: 5 "healthy-only" runs (for twin training) and
     3 "full trajectory" runs (healthy through critical, for later testing).

2. ml/digital_twin.py
   - Input features (twin inputs): rpm, throttle, map, altitude, ambient_temp
   - Output targets (twin outputs): egt, cht, oil_pressure, oil_temp,
     vibration, fuel_flow
   - Train one regressor per output (or one multi-output regressor) using
     gradient-boosted trees (XGBoost or LightGBM), fit ONLY on the
     healthy-only runs.
   - Expose: predict(sample: dict) -> dict returning expected values for
     the twin-output fields, per section 4.
   - Save the trained model to ml/artifacts/.

3. backend/residual.py
   - compute(actual: dict, expected: dict) -> dict
   - Returns residual (actual - expected) and residual_z (residual /
     std_healthy, where std_healthy is computed from residuals on the
     healthy-only runs), per section 6.
   - Output shape must match the example JSON in section 6 exactly
     (actual / expected / residual / residual_z keys).

Acceptance test (write this as a script or notebook in tests/ or root):
   - Replay one full-trajectory run sample-by-sample through Digital Twin
     -> Residual Engine.
   - Plot actual vs expected vs residual for at least egt and oil_pressure
     across the run.
   - Confirm visually: expected values track operating-condition changes
     (not flat), and residuals visibly increase as degradation_stage
     progresses from healthy to critical.

Do not build the dashboard, API, or AI PHM (anomaly/RUL) models yet —
that's Phase 1B. Stop once the acceptance test plot looks right and
commit.
```

---

# Phase 1B — AI PHM Core Specification

Consumes `residual_z` from `backend/residual.py`. Produces the four capabilities Antigravity already identified: anomaly detection, fault/degradation classification, Health Index, RUL. Below is the concrete design for each, plus the one thing Antigravity's summary didn't specify yet: how they combine into a single output and how RUL is actually labeled for training.

## 1. Training Data Prep (do this first — nothing else works without it)

Write `ml/prepare_phm_dataset.py`:

- Load all **full-trajectory runs** from `simulation/`.
- For each sample: run `digital_twin.predict()` → `residual.compute()` → get `residual_z` (6 values).
- Attach two label columns already present in the raw data:
  - `degradation_stage` (categorical, ground truth) — for the classifier.
  - `rul_hours` — **not in the raw data yet, compute it**: for each run, `rul_hours = run_total_hours_to_critical - engine_hours` at that sample. Since these are synthetic trajectory runs, the point at which each run reaches `critical` is known, so this is a straightforward per-run subtraction.
- Also pull healthy-only runs' `residual_z` separately (no labels needed) — used for the anomaly detector.
- Output: `data/phm_training_table.csv` with columns `residual_z_egt, residual_z_cht, residual_z_oil_pressure, residual_z_oil_temp, residual_z_vibration, residual_z_fuel_flow, engine_hours, degradation_stage, rul_hours`.

## 2. Anomaly Detector (`ml/anomaly_detector.py`)

- **Model:** Isolation Forest (unsupervised), fit on `residual_z` from healthy-only runs only.
- **Interface:** `predict(residual_z: dict) -> dict` → `{"is_anomalous": bool, "anomaly_score": float}` (score = model's decision function, normalized to roughly 0–1 where higher = more anomalous).
- Threshold for `is_anomalous`: pick from the healthy-data score distribution (e.g. flag anything beyond the 99th percentile of healthy scores) — don't hardcode an arbitrary number.

## 3. Fault / Degradation Classifier (`ml/fault_classifier.py`)

- **Model:** Random Forest or XGBoost multi-class classifier.
- **Input:** `residual_z` (6-dim vector). Optionally include `engine_hours` as a feature — it's known at inference time, so this isn't leakage.
- **Target:** `degradation_stage` (5 classes: healthy, early_deviation, incipient_degradation, progressive_degradation, critical).
- **Interface:** `predict(residual_z: dict, engine_hours: float = None) -> dict` → `{"stage": str, "confidence": float, "class_probabilities": dict}`.
- Train/test split **by run**, not by row (don't let samples from the same trajectory run leak across train/test — that inflates accuracy artificially).

## 4. RUL Estimator (`ml/rul_estimator.py`)

- **Model:** XGBoost regressor (matches the twin's model family, keeps the stack consistent).
- **Input:** `residual_z` (6-dim) + `engine_hours`.
- **Target:** `rul_hours` (computed in step 1).
- **Confidence interval:** train two additional quantile-regression models (10th and 90th percentile) alongside the point estimate — XGBoost supports quantile loss directly. This gives `rul_hours ± range` instead of a bare number, matching the "confidence-aware decision making" requirement from the original spec (section 14).
- **Interface:** `predict(residual_z: dict, engine_hours: float) -> dict` → `{"rul_hours": float, "rul_lower": float, "rul_upper": float}`.

## 5. Health Index (`ml/health_index.py`) — no separate model, a combination function

Health Index is a deterministic function of the outputs above, not its own ML model:

```
stage_base = {healthy: 100, early_deviation: 80, incipient_degradation: 55,
              progressive_degradation: 30, critical: 5}[predicted_stage]

health_index = stage_base
               - (anomaly_score * 15)          # penalize high anomaly within a stage
               * stage_confidence                # scale by classifier confidence
```

This keeps Health Index smooth within a stage (not a hard jump at stage boundaries) while still anchored to the classifier's prediction. Clamp to [0, 100].

## 6. Integration Wrapper (`ml/phm_core.py`)

Single entry point combining all four, so downstream (Mission Analyzer, dashboard) only calls one function:

```
predict(residual_z: dict, engine_hours: float) -> dict
{
  "anomaly": bool,
  "anomaly_score": float,
  "degradation_stage": str,
  "stage_confidence": float,
  "health_index": float,
  "rul_hours": float,
  "rul_confidence_interval": [lower, upper]
}
```

## 7. Acceptance Test

Replay one full-trajectory run through `digital_twin → residual → phm_core`, plot over time:
- `health_index` (should trend downward, roughly matching ground-truth `degradation_stage` progression)
- `rul_hours` (should trend toward 0 as the run approaches `critical`)
- predicted `degradation_stage` vs ground-truth `degradation_stage` (should mostly agree, especially in later stages)

That's the Phase 1B proof point: **"Residual → Health/Degradation/RUL works."**

---

## What to tell Antigravity (Day 2 / Phase 1B build prompt)

```
Project: uav-engine-digital-twin
Context: Full spec is in docs/phase1a-telemetry-digital-twin-spec.md, Phase 1B
section — read it first and follow it exactly. Phase 1A (telemetry_generator.py,
digital_twin.py, residual.py) is already built and working — reuse it, do not
modify its interfaces.

Build, in order:

1. ml/prepare_phm_dataset.py
   - Run all full-trajectory runs through digital_twin.predict() and
     residual.compute() to get residual_z per sample.
   - Compute rul_hours per sample = run's total hours to critical - engine_hours
     at that sample.
   - Save data/phm_training_table.csv with residual_z (6 cols), engine_hours,
     degradation_stage, rul_hours.

2. ml/anomaly_detector.py
   - Isolation Forest, fit on residual_z from healthy-only runs only.
   - predict(residual_z: dict) -> {"is_anomalous": bool, "anomaly_score": float}
   - Threshold is_anomalous at the 99th percentile of healthy anomaly scores.

3. ml/fault_classifier.py
   - RandomForest or XGBoost multi-class classifier, residual_z (+ engine_hours)
     -> degradation_stage (5 classes).
   - Split train/test BY RUN, not by row.
   - predict(residual_z, engine_hours=None) -> {"stage": str, "confidence": float,
     "class_probabilities": dict}

4. ml/rul_estimator.py
   - XGBoost regressor, residual_z + engine_hours -> rul_hours.
   - Also train 10th/90th percentile quantile-loss XGBoost models for a
     confidence interval.
   - predict(residual_z, engine_hours) -> {"rul_hours": float, "rul_lower": float,
     "rul_upper": float}

5. ml/health_index.py
   - Deterministic function (not a trained model):
     stage_base = {healthy:100, early_deviation:80, incipient_degradation:55,
                   progressive_degradation:30, critical:5}[stage]
     health_index = clamp(stage_base - anomaly_score*15, 0, 100) * stage_confidence
     (clamp final result to [0,100] too)

6. ml/phm_core.py
   - Single entry point: predict(residual_z: dict, engine_hours: float) -> dict
     combining all four above into one flat response:
     {"anomaly": bool, "anomaly_score": float, "degradation_stage": str,
      "stage_confidence": float, "health_index": float, "rul_hours": float,
      "rul_confidence_interval": [lower, upper]}

Acceptance test:
   - Replay one full-trajectory run through digital_twin -> residual -> phm_core.
   - Plot health_index and rul_hours over the run.
   - Plot predicted vs ground-truth degradation_stage over the run.
   - Confirm: health_index trends down, rul_hours trends toward 0 near critical,
     predicted stage broadly tracks ground truth (especially later stages).

Do not build Mission Analyzer, Mission Risk, or the dashboard yet — that's
Phase 3. Stop once the acceptance test plots look right and commit.
```

