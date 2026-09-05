"""
Fault / Degradation Classifier
================================

XGBoost multi-class classifier that maps ``residual_z`` (+ optionally
``engine_hours``) to one of the 5 degradation stages.

Training uses a **by-run** train/test split so no trajectory leaks
across partitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder

from ml.digital_twin import TWIN_OUTPUTS

RESIDUAL_Z_COLS = [f"residual_z_{s}" for s in TWIN_OUTPUTS]
FEATURE_COLS = RESIDUAL_Z_COLS + ["engine_hours"]

DEGRADATION_STAGES = [
    "healthy",
    "early_deviation",
    "incipient_degradation",
    "progressive_degradation",
    "critical",
]


class FaultClassifier:
    """XGBoost multi-class degradation-stage classifier.

    Parameters
    ----------
    model : XGBClassifier | None
        Fitted classifier.
    label_encoder : LabelEncoder | None
        Maps stage strings ↔ integer class indices.
    """

    def __init__(
        self,
        model: Optional[XGBClassifier] = None,
        label_encoder: Optional[LabelEncoder] = None,
    ):
        self.model = model
        self.label_encoder = label_encoder or LabelEncoder()

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        training_table_path: str | Path = "data/phm_training_table.csv",
        test_run_id: int = 3,
        xgb_params: Optional[dict] = None,
    ) -> "FaultClassifier":
        """Train on trajectory data, split by run (not by row).

        Parameters
        ----------
        training_table_path : path
            CSV produced by ``prepare_phm_dataset.py``.
        test_run_id : int
            Run ID to hold out for testing (all others are training).
        """
        df = pd.read_csv(training_table_path)

        # Encode labels
        self.label_encoder.fit(DEGRADATION_STAGES)
        df["label"] = self.label_encoder.transform(df["degradation_stage"])

        # Split by run
        train_df = df[df["run_id"] != test_run_id]
        test_df = df[df["run_id"] == test_run_id]

        X_train = train_df[FEATURE_COLS].values
        y_train = train_df["label"].values
        X_test = test_df[FEATURE_COLS].values
        y_test = test_df["label"].values

        print(f"  Train: {len(X_train):,} samples (runs != {test_run_id})")
        print(f"  Test:  {len(X_test):,} samples  (run {test_run_id})")

        params = {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "use_label_encoder": False,
            "eval_metric": "mlogloss",
            "verbosity": 0,
        }
        if xgb_params:
            params.update(xgb_params)

        self.model = XGBClassifier(**params)
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        stage_names = self.label_encoder.classes_
        report = classification_report(y_test, y_pred, target_names=stage_names)
        print(f"\n  Classification Report (test run {test_run_id}):\n")
        print(report)

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(
        self,
        residual_z: dict,
        engine_hours: float = None,
    ) -> dict:
        """Predict degradation stage for a single sample.

        Parameters
        ----------
        residual_z : dict
            Keys are sensor names, values are z-scores.
        engine_hours : float, optional
            Current engine hours. If None, defaults to 0.

        Returns
        -------
        dict  ``{"stage": str, "confidence": float, "class_probabilities": dict}``
        """
        features = [residual_z[s] for s in TWIN_OUTPUTS]
        features.append(engine_hours if engine_hours is not None else 0.0)
        x = np.array([features])

        proba = self.model.predict_proba(x)[0]
        pred_idx = int(np.argmax(proba))
        stage = self.label_encoder.inverse_transform([pred_idx])[0]
        confidence = float(proba[pred_idx])

        class_probs = {
            self.label_encoder.inverse_transform([i])[0]: round(float(p), 4)
            for i, p in enumerate(proba)
        }

        return {
            "stage": stage,
            "confidence": round(confidence, 4),
            "class_probabilities": class_probs,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, artifacts_dir: str | Path = "ml/artifacts") -> None:
        artifacts_dir = Path(artifacts_dir)
        joblib.dump(self.model, artifacts_dir / "fault_classifier.joblib")
        with open(artifacts_dir / "fault_classifier_classes.json", "w") as f:
            json.dump(list(self.label_encoder.classes_), f)
        print(f"  Saved fault classifier to {artifacts_dir}/")

    @classmethod
    def load(cls, artifacts_dir: str | Path = "ml/artifacts") -> "FaultClassifier":
        artifacts_dir = Path(artifacts_dir)
        model = joblib.load(artifacts_dir / "fault_classifier.joblib")
        with open(artifacts_dir / "fault_classifier_classes.json", "r") as f:
            classes = json.load(f)
        le = LabelEncoder()
        le.classes_ = np.array(classes)
        return cls(model=model, label_encoder=le)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Training Fault Classifier...\n")
    clf = FaultClassifier()
    clf.train()
    clf.save()
    print("\nDone.")
