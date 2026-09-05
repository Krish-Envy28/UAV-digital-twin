"""
Residual Engine
================

Computes raw and normalized residuals between actual sensor readings and
the Digital Twin's expected (healthy) predictions.

The normalized residual vector ``residual_z`` is the primary signal consumed
by all downstream Phase 1B+ modules:
  - Anomaly detector (threshold / statistical test on z-scores)
  - Fault classifier (pattern of z-scores across sensors)
  - Health index (aggregate of z-score magnitudes)
  - RUL estimator (trend of z-scores over time)

Phase 1B+ compatibility notes
------------------------------
- ``compute()`` returns a flat dict with ``actual``, ``expected``,
  ``residual``, and ``residual_z`` sub-dicts — easy to serialize to JSON
  for the streaming API (Phase 3) or feed into a DataFrame for batch
  analysis (Phase 1B).
- ``compute_batch()`` operates on DataFrames for efficient bulk processing.
- ``ResidualEngine`` is stateless except for ``std_healthy`` — it can be
  shared across threads or wrapped in a FastAPI endpoint trivially.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

TWIN_OUTPUTS = ["egt", "cht", "oil_pressure", "oil_temp", "vibration", "fuel_flow"]


class ResidualEngine:
    """
    Computes residuals between actual sensor readings and digital-twin
    expected values.

    Parameters
    ----------
    std_healthy : dict[str, float]
        Per-sensor residual standard deviation observed on healthy data.
        Used to compute the normalized z-score residuals.
    """

    def __init__(self, std_healthy: Dict[str, float]):
        self.std_healthy = std_healthy
        # Guard against zero std (would cause division by zero)
        for sensor in TWIN_OUTPUTS:
            if self.std_healthy.get(sensor, 0) == 0:
                self.std_healthy[sensor] = 1e-6

    @classmethod
    def from_file(cls, path: str | Path = "ml/artifacts/std_healthy.json") -> "ResidualEngine":
        """Load std_healthy from the JSON file saved during twin training."""
        with open(path, "r") as f:
            std_healthy = json.load(f)
        return cls(std_healthy)

    def compute(self, actual: dict, expected: dict) -> dict:
        """
        Compute residuals for a single sample.

        Parameters
        ----------
        actual : dict
            Actual sensor readings (must contain TWIN_OUTPUTS keys).
        expected : dict
            Digital Twin predicted values (must contain TWIN_OUTPUTS keys).

        Returns
        -------
        dict with structure::

            {
                "actual":     {"egt": ..., "cht": ..., ...},
                "expected":   {"egt": ..., "cht": ..., ...},
                "residual":   {"egt": ..., "cht": ..., ...},
                "residual_z": {"egt": ..., "cht": ..., ...}
            }
        """
        residual = {}
        residual_z = {}

        for sensor in TWIN_OUTPUTS:
            r = actual[sensor] - expected[sensor]
            residual[sensor] = round(r, 4)
            residual_z[sensor] = round(r / self.std_healthy[sensor], 4)

        return {
            "actual": {s: actual[s] for s in TWIN_OUTPUTS},
            "expected": {s: expected[s] for s in TWIN_OUTPUTS},
            "residual": residual,
            "residual_z": residual_z,
        }

    def compute_batch(
        self,
        actual_df: pd.DataFrame,
        expected_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Batch residual computation (for Phase 1B training pipelines).

        Returns a DataFrame with columns:
          ``{sensor}_residual`` and ``{sensor}_z`` for each twin-output sensor.
        """
        result = pd.DataFrame(index=actual_df.index)
        for sensor in TWIN_OUTPUTS:
            r = actual_df[sensor] - expected_df[sensor]
            result[f"{sensor}_residual"] = r
            result[f"{sensor}_z"] = r / self.std_healthy[sensor]
        return result
