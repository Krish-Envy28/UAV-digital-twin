"""
Anomaly Detector
=================

Isolation Forest trained on residual_z from healthy-only engine runs.
Flags whether a new sample is anomalous (outside the learned healthy
distribution) and returns a normalised anomaly score (0 = normal, 1 = extreme).

Threshold for ``is_anomalous`` is set at the 99th percentile of the
healthy-data anomaly-score distribution (data-driven, not hardcoded).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ml.digital_twin import TWIN_OUTPUTS

RESIDUAL_Z_COLS = [f"residual_z_{s}" for s in TWIN_OUTPUTS]


class AnomalyDetector:
    """Isolation-Forest anomaly detector over the 6-dim residual_z vector.

    Parameters
    ----------
    model : IsolationForest | None
        Fitted Isolation Forest.
    threshold : float
        Anomaly-score threshold (scores above this ⇒ anomalous).
    score_shift, score_scale : float
        Used to map sklearn's raw ``decision_function`` to [0, 1].
    """

    def __init__(
        self,
        model: Optional[IsolationForest] = None,
        threshold: float = 0.5,
        score_shift: float = 0.0,
        score_scale: float = 1.0,
    ):
        self.model = model
        self.threshold = threshold
        self.score_shift = score_shift
        self.score_scale = score_scale

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        healthy_residuals_path: str | Path = "data/healthy_residuals.csv",
        contamination: float = 0.01,
        random_state: int = 42,
    ) -> "AnomalyDetector":
        """Fit on healthy-only residual_z.

        Parameters
        ----------
        healthy_residuals_path : path
            CSV with ``residual_z_*`` columns (produced by prepare_phm_dataset).
        contamination : float
            Expected fraction of outliers in healthy data (used by IF).
        """
        df = pd.read_csv(healthy_residuals_path)
        X = df[RESIDUAL_Z_COLS].values

        print(f"  Training Isolation Forest on {len(X):,} healthy samples ...")
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self.model.fit(X)

        # Raw decision_function: large positive = inlier, large negative = outlier.
        # We invert & normalise so 0 = perfectly normal, 1 = extreme outlier.
        raw_scores = self.model.decision_function(X)
        self.score_shift = float(np.max(raw_scores))  # shift so max healthy ≈ 0
        self.score_scale = float(np.abs(np.min(raw_scores) - np.max(raw_scores))) or 1.0

        normalised = self._normalise(raw_scores)

        # Threshold at 99th percentile of healthy normalised scores
        self.threshold = float(np.percentile(normalised, 99))
        print(f"  Anomaly threshold (99th pct of healthy): {self.threshold:.4f}")

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _normalise(self, raw_scores: np.ndarray) -> np.ndarray:
        """Map raw decision_function values to roughly [0, 1]."""
        normed = (self.score_shift - raw_scores) / self.score_scale
        return np.clip(normed, 0.0, 1.0)

    def predict(self, residual_z: dict) -> dict:
        """Predict anomaly status for a single sample.

        Parameters
        ----------
        residual_z : dict
            Keys are sensor names (egt, cht, …), values are z-scores.

        Returns
        -------
        dict  ``{"is_anomalous": bool, "anomaly_score": float}``
        """
        x = np.array([[residual_z[s] for s in TWIN_OUTPUTS]])
        raw = self.model.decision_function(x)
        score = float(self._normalise(raw)[0])
        return {
            "is_anomalous": score > self.threshold,
            "anomaly_score": round(score, 4),
        }

    def predict_batch(self, residual_z_df: pd.DataFrame) -> pd.DataFrame:
        """Batch inference. Returns DataFrame with ``anomaly_score`` and ``is_anomalous``."""
        X = residual_z_df[RESIDUAL_Z_COLS].values
        raw = self.model.decision_function(X)
        scores = self._normalise(raw)
        return pd.DataFrame({
            "anomaly_score": np.round(scores, 4),
            "is_anomalous": scores > self.threshold,
        }, index=residual_z_df.index)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, artifacts_dir: str | Path = "ml/artifacts") -> None:
        artifacts_dir = Path(artifacts_dir)
        joblib.dump(self.model, artifacts_dir / "anomaly_detector.joblib")
        with open(artifacts_dir / "anomaly_meta.json", "w") as f:
            json.dump({
                "threshold": self.threshold,
                "score_shift": self.score_shift,
                "score_scale": self.score_scale,
            }, f, indent=2)
        print(f"  Saved anomaly detector to {artifacts_dir}/")

    @classmethod
    def load(cls, artifacts_dir: str | Path = "ml/artifacts") -> "AnomalyDetector":
        artifacts_dir = Path(artifacts_dir)
        model = joblib.load(artifacts_dir / "anomaly_detector.joblib")
        with open(artifacts_dir / "anomaly_meta.json", "r") as f:
            meta = json.load(f)
        return cls(
            model=model,
            threshold=meta["threshold"],
            score_shift=meta["score_shift"],
            score_scale=meta["score_scale"],
        )


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Training Anomaly Detector...\n")
    detector = AnomalyDetector()
    detector.train()
    detector.save()
    print("\nDone.")
