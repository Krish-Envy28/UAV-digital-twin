"""
Digital Twin — Expected-Value Model
====================================

Trains one XGBRegressor per twin-output sensor on healthy-only data.
Exposes a single ``predict(sample) -> dict`` interface that returns the
expected sensor values for a healthy engine under the given operating
conditions.

Phase 1B+ compatibility notes
------------------------------
- ``predict()`` returns a plain dict — any downstream module (anomaly
  detector, fault classifier, health-index calculator) can consume it
  directly.
- The model is saved/loaded via ``joblib``, so it can be swapped for an
  LSTM or neural-net later without changing the interface.
- ``std_healthy`` (per-sensor residual standard deviation on healthy data)
  is computed and persisted at training time and can be loaded by the
  Residual Engine or any Phase 1B module that needs normalization.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

# ---------------------------------------------------------------------------
# Schema (shared with telemetry_generator — could be factored into a
# shared constants module later, but kept local for Phase 1A simplicity).
# ---------------------------------------------------------------------------

TWIN_INPUTS = ["rpm", "throttle", "map", "altitude", "ambient_temp"]
TWIN_OUTPUTS = ["egt", "cht", "oil_pressure", "oil_temp", "vibration", "fuel_flow"]


# ---------------------------------------------------------------------------
# Digital Twin class
# ---------------------------------------------------------------------------

class DigitalTwin:
    """
    Condition-aware expected-value model for a UAV piston engine.

    The twin learns the mapping ``operating_conditions -> healthy_sensor_values``
    so that deviations (residuals) from the prediction indicate degradation.

    Parameters
    ----------
    models : dict[str, XGBRegressor] | None
        Pre-trained models keyed by output sensor name. ``None`` if not yet
        trained.
    std_healthy : dict[str, float] | None
        Per-sensor residual standard deviation observed on healthy data.
    """

    def __init__(
        self,
        models: Optional[Dict[str, XGBRegressor]] = None,
        std_healthy: Optional[Dict[str, float]] = None,
    ):
        self.models: Dict[str, XGBRegressor] = models or {}
        self.std_healthy: Dict[str, float] = std_healthy or {}

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        healthy_files: List[str | Path],
        xgb_params: Optional[dict] = None,
    ) -> "DigitalTwin":
        """
        Train one XGBRegressor per twin-output sensor on healthy-only data.

        Parameters
        ----------
        healthy_files : list of paths
            JSONL files containing healthy-only telemetry data.
        xgb_params : dict, optional
            Override XGBRegressor hyperparameters.

        Returns
        -------
        self (for chaining)
        """
        # -- Load data --
        frames = []
        for fpath in healthy_files:
            with open(fpath, "r") as f:
                records = [json.loads(line) for line in f]
            frames.append(pd.DataFrame(records))
        df = pd.concat(frames, ignore_index=True)

        print(f"  Training on {len(df):,} healthy samples from {len(healthy_files)} files")

        X = df[TWIN_INPUTS].values
        params = {
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "verbosity": 0,
        }
        if xgb_params:
            params.update(xgb_params)

        # -- Train per-sensor models --
        self.models = {}
        residuals_healthy: Dict[str, np.ndarray] = {}

        for sensor in TWIN_OUTPUTS:
            y = df[sensor].values
            model = XGBRegressor(**params)
            model.fit(X, y)
            self.models[sensor] = model

            # Compute residuals on training data (for std_healthy)
            y_pred = model.predict(X)
            residuals_healthy[sensor] = y - y_pred
            print(f"    {sensor:16s}  MAE={np.mean(np.abs(y - y_pred)):.3f}")

        # -- Compute std_healthy (used by Residual Engine for z-scores) --
        self.std_healthy = {
            sensor: float(np.std(residuals_healthy[sensor]))
            for sensor in TWIN_OUTPUTS
        }
        print(f"  std_healthy: { {k: round(v, 4) for k, v in self.std_healthy.items()} }")

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, sample: dict) -> dict:
        """
        Predict expected healthy sensor values for the given operating
        conditions.

        Parameters
        ----------
        sample : dict
            Must contain at least the TWIN_INPUTS keys.

        Returns
        -------
        dict
            Predicted values for each TWIN_OUTPUTS key, e.g.:
            ``{"egt": 702.1, "cht": 165.3, ...}``
        """
        x = np.array([[sample[k] for k in TWIN_INPUTS]])
        return {
            sensor: round(float(self.models[sensor].predict(x)[0]), 2)
            for sensor in TWIN_OUTPUTS
        }

    def predict_batch(self, samples: pd.DataFrame) -> pd.DataFrame:
        """
        Batch prediction for efficiency (useful in Phase 1B training
        pipelines where you need residuals for an entire dataset).

        Parameters
        ----------
        samples : pd.DataFrame
            Must contain TWIN_INPUTS columns.

        Returns
        -------
        pd.DataFrame with columns for each TWIN_OUTPUTS sensor.
        """
        X = samples[TWIN_INPUTS].values
        result = {}
        for sensor in TWIN_OUTPUTS:
            result[sensor] = self.models[sensor].predict(X)
        return pd.DataFrame(result, index=samples.index)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, artifacts_dir: str | Path = "ml/artifacts") -> None:
        """Save trained models and std_healthy to disk."""
        artifacts_dir = Path(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        for sensor, model in self.models.items():
            joblib.dump(model, artifacts_dir / f"twin_{sensor}.joblib")

        with open(artifacts_dir / "std_healthy.json", "w") as f:
            json.dump(self.std_healthy, f, indent=2)

        print(f"  Models saved to {artifacts_dir}/")

    @classmethod
    def load(cls, artifacts_dir: str | Path = "ml/artifacts") -> "DigitalTwin":
        """Load a previously trained DigitalTwin from disk."""
        artifacts_dir = Path(artifacts_dir)

        models = {}
        for sensor in TWIN_OUTPUTS:
            model_path = artifacts_dir / f"twin_{sensor}.joblib"
            if not model_path.exists():
                raise FileNotFoundError(f"Missing model file: {model_path}")
            models[sensor] = joblib.load(model_path)

        with open(artifacts_dir / "std_healthy.json", "r") as f:
            std_healthy = json.load(f)

        return cls(models=models, std_healthy=std_healthy)


# ---------------------------------------------------------------------------
# CLI: train and save
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path

    data_dir = Path("data")
    healthy_files = sorted(data_dir.glob("healthy_run_*.jsonl"))

    if not healthy_files:
        print("ERROR: No healthy_run_*.jsonl files found in data/. "
              "Run the telemetry generator first.")
        raise SystemExit(1)

    print("Training Digital Twin...\n")
    twin = DigitalTwin()
    twin.train([str(f) for f in healthy_files])
    twin.save()
    print("\nDone.")
