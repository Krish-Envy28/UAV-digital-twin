"""
Remaining Useful Life (RUL) Estimator
=======================================

XGBoost regressor that predicts how many engine-hours remain before the
engine reaches the ``critical`` degradation stage.

Three models are trained:
  - **Point estimate** — standard squared-error loss.
  - **Lower bound (10th percentile)** — quantile loss, α = 0.1.
  - **Upper bound (90th percentile)** — quantile loss, α = 0.9.

Together they give ``rul_hours +/- [lower, upper]`` — a confidence-aware
prediction required by the spec for mission risk decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.digital_twin import TWIN_OUTPUTS

RESIDUAL_Z_COLS = [f"residual_z_{s}" for s in TWIN_OUTPUTS]
FEATURE_COLS = RESIDUAL_Z_COLS + ["engine_hours"]


class RULEstimator:
    """XGBoost RUL regressor with quantile-based confidence interval.

    Parameters
    ----------
    model_point : XGBRegressor | None
        Point-estimate model (squared-error).
    model_lower : XGBRegressor | None
        10th-percentile quantile model.
    model_upper : XGBRegressor | None
        90th-percentile quantile model.
    """

    def __init__(
        self,
        model_point: Optional[XGBRegressor] = None,
        model_lower: Optional[XGBRegressor] = None,
        model_upper: Optional[XGBRegressor] = None,
    ):
        self.model_point = model_point
        self.model_lower = model_lower
        self.model_upper = model_upper

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        training_table_path: str | Path = "data/phm_training_table.csv",
        test_run_id: int = 3,
        xgb_params: Optional[dict] = None,
    ) -> "RULEstimator":
        """Train point + quantile models, split by run.

        Parameters
        ----------
        training_table_path : path
            CSV produced by ``prepare_phm_dataset.py``.
        test_run_id : int
            Run ID to hold out for testing.
        """
        df = pd.read_csv(training_table_path)

        train_df = df[df["run_id"] != test_run_id]
        test_df = df[df["run_id"] == test_run_id]

        X_train = train_df[FEATURE_COLS].values
        y_train = train_df["rul_hours"].values
        X_test = test_df[FEATURE_COLS].values
        y_test = test_df["rul_hours"].values

        print(f"  Train: {len(X_train):,} samples, Test: {len(X_test):,} samples")

        base_params = {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "verbosity": 0,
        }
        if xgb_params:
            base_params.update(xgb_params)

        # --- Point estimate (MSE) ---
        print("  Training point-estimate model (squared error)...")
        self.model_point = XGBRegressor(**base_params)
        self.model_point.fit(X_train, y_train)

        y_pred = self.model_point.predict(X_test)
        mae = float(np.mean(np.abs(y_test - y_pred)))
        print(f"    Test MAE: {mae:.2f} hours")

        # --- Lower quantile (10th pct) ---
        print("  Training lower-bound model (10th percentile)...")
        lower_params = {**base_params, "objective": "reg:quantileerror", "quantile_alpha": 0.1}
        self.model_lower = XGBRegressor(**lower_params)
        self.model_lower.fit(X_train, y_train)

        # --- Upper quantile (90th pct) ---
        print("  Training upper-bound model (90th percentile)...")
        upper_params = {**base_params, "objective": "reg:quantileerror", "quantile_alpha": 0.9}
        self.model_upper = XGBRegressor(**upper_params)
        self.model_upper.fit(X_train, y_train)

        # Quick sanity: show interval width on test set
        y_lower = self.model_lower.predict(X_test)
        y_upper = self.model_upper.predict(X_test)
        avg_width = float(np.mean(y_upper - y_lower))
        print(f"    Avg 80% confidence interval width: {avg_width:.1f} hours")

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, residual_z: dict, engine_hours: float) -> dict:
        """Predict RUL with confidence interval for a single sample.

        Parameters
        ----------
        residual_z : dict
            Keys are sensor names, values are z-scores.
        engine_hours : float
            Current engine hours.

        Returns
        -------
        dict  ``{"rul_hours": float, "rul_lower": float, "rul_upper": float}``
        """
        features = [residual_z[s] for s in TWIN_OUTPUTS]
        features.append(engine_hours)
        x = np.array([features])

        point = float(self.model_point.predict(x)[0])
        lower = float(self.model_lower.predict(x)[0])
        upper = float(self.model_upper.predict(x)[0])

        # Clamp: RUL can't be negative
        point = max(point, 0.0)
        lower = max(lower, 0.0)
        upper = max(upper, 0.0)

        # Ensure lower <= point <= upper
        lower = min(lower, point)
        upper = max(upper, point)

        return {
            "rul_hours": round(point, 2),
            "rul_lower": round(lower, 2),
            "rul_upper": round(upper, 2),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, artifacts_dir: str | Path = "ml/artifacts") -> None:
        artifacts_dir = Path(artifacts_dir)
        joblib.dump(self.model_point, artifacts_dir / "rul_point.joblib")
        joblib.dump(self.model_lower, artifacts_dir / "rul_lower.joblib")
        joblib.dump(self.model_upper, artifacts_dir / "rul_upper.joblib")
        print(f"  Saved RUL estimator (3 models) to {artifacts_dir}/")

    @classmethod
    def load(cls, artifacts_dir: str | Path = "ml/artifacts") -> "RULEstimator":
        artifacts_dir = Path(artifacts_dir)
        return cls(
            model_point=joblib.load(artifacts_dir / "rul_point.joblib"),
            model_lower=joblib.load(artifacts_dir / "rul_lower.joblib"),
            model_upper=joblib.load(artifacts_dir / "rul_upper.joblib"),
        )


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Training RUL Estimator...\n")
    est = RULEstimator()
    est.train()
    est.save()
    print("\nDone.")
