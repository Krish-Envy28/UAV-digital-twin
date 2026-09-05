"""
PHM Training Dataset Preparation
==================================

Converts raw telemetry runs into the labeled feature table that all
Phase 1B models train on.

Two outputs:
  - ``data/phm_training_table.csv`` — trajectory-run samples with
    residual_z (6 cols), engine_hours, degradation_stage, rul_hours, run_id.
  - ``data/healthy_residuals.csv``  — healthy-run residual_z only
    (for the anomaly detector's unsupervised fit).

This script must be run *after* Phase 1A's digital-twin training
(``ml/artifacts/`` must contain the saved models and ``std_healthy.json``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd

from ml.digital_twin import DigitalTwin, TWIN_OUTPUTS
from backend.residual import ResidualEngine

# Residual-z column names used throughout Phase 1B
RESIDUAL_Z_COLS = [f"residual_z_{s}" for s in TWIN_OUTPUTS]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _load_jsonl(path: str | Path) -> pd.DataFrame:
    """Load a JSONL file into a DataFrame."""
    records = []
    with open(path, "r") as f:
        for line in f:
            records.append(json.loads(line))
    return pd.DataFrame(records)


def _find_first_critical_hours(df: pd.DataFrame) -> float:
    """Return the engine_hours at which the run first reaches 'critical'.

    If no critical sample exists (healthy-only run), returns ``float('inf')``.
    """
    critical = df[df["degradation_stage"] == "critical"]
    if critical.empty:
        return float("inf")
    return float(critical["engine_hours"].iloc[0])


def _compute_residual_z(
    df: pd.DataFrame,
    twin: DigitalTwin,
    residual_engine: ResidualEngine,
) -> pd.DataFrame:
    """Run batch predict → residual for an entire run DataFrame.

    Returns a DataFrame with one ``residual_z_{sensor}`` column per output
    sensor, aligned to ``df.index``.
    """
    expected_df = twin.predict_batch(df)
    actual_df = df[TWIN_OUTPUTS]
    residuals_df = residual_engine.compute_batch(actual_df, expected_df)

    # Rename from ``{sensor}_z`` to ``residual_z_{sensor}`` for clarity
    rename_map = {f"{s}_z": f"residual_z_{s}" for s in TWIN_OUTPUTS}
    rz = residuals_df[[f"{s}_z" for s in TWIN_OUTPUTS]].rename(columns=rename_map)
    return rz


# ------------------------------------------------------------------
# Main dataset builder
# ------------------------------------------------------------------

def prepare_datasets(
    data_dir: str | Path = "data",
    artifacts_dir: str | Path = "ml/artifacts",
) -> dict:
    """Build both PHM training tables.

    Returns
    -------
    dict with keys ``training_table_path`` and ``healthy_residuals_path``.
    """
    data_dir = Path(data_dir)
    twin = DigitalTwin.load(artifacts_dir)
    residual_engine = ResidualEngine.from_file(Path(artifacts_dir) / "std_healthy.json")

    # ---- Trajectory runs → labeled table ----
    trajectory_files = sorted(data_dir.glob("trajectory_run_*.jsonl"))
    if not trajectory_files:
        raise FileNotFoundError("No trajectory_run_*.jsonl found in data/")

    trajectory_frames: List[pd.DataFrame] = []

    for idx, fpath in enumerate(trajectory_files, start=1):
        print(f"  Processing {fpath.name} (run {idx})...")
        df = _load_jsonl(fpath)

        # Compute residual_z
        rz = _compute_residual_z(df, twin, residual_engine)

        # Find the hour at which this run first hits critical
        critical_hours = _find_first_critical_hours(df)
        if critical_hours == float("inf"):
            print(f"    WARNING: {fpath.name} never reaches critical — skipping RUL")
            rul = pd.Series([None] * len(df), name="rul_hours")
        else:
            rul = critical_hours - df["engine_hours"]
            rul.name = "rul_hours"
            print(f"    First critical at {critical_hours:.1f} h")

        frame = pd.concat([
            rz.reset_index(drop=True),
            df[["engine_hours", "degradation_stage"]].reset_index(drop=True),
            rul.reset_index(drop=True),
        ], axis=1)
        frame["run_id"] = idx
        trajectory_frames.append(frame)

    training_table = pd.concat(trajectory_frames, ignore_index=True)
    training_path = data_dir / "phm_training_table.csv"
    training_table.to_csv(training_path, index=False)
    print(f"\n  Saved {training_path}  ({len(training_table):,} rows, "
          f"{len(training_table.columns)} cols)")

    # ---- Healthy runs → unlabeled residual_z ----
    healthy_files = sorted(data_dir.glob("healthy_run_*.jsonl"))
    if not healthy_files:
        raise FileNotFoundError("No healthy_run_*.jsonl found in data/")

    healthy_frames: List[pd.DataFrame] = []
    for fpath in healthy_files:
        print(f"  Processing {fpath.name} (healthy)...")
        df = _load_jsonl(fpath)
        rz = _compute_residual_z(df, twin, residual_engine)
        healthy_frames.append(rz)

    healthy_rz = pd.concat(healthy_frames, ignore_index=True)
    healthy_path = data_dir / "healthy_residuals.csv"
    healthy_rz.to_csv(healthy_path, index=False)
    print(f"  Saved {healthy_path}  ({len(healthy_rz):,} rows)")

    return {
        "training_table_path": str(training_path),
        "healthy_residuals_path": str(healthy_path),
    }


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Preparing PHM training datasets...\n")
    result = prepare_datasets()
    print(f"\nDone.\n  Training table: {result['training_table_path']}\n"
          f"  Healthy residuals: {result['healthy_residuals_path']}")
