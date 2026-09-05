"""
PHM Core — Unified Prognostic Health Management Entry Point
=============================================================

Combines all four Phase 1B capabilities into a single ``predict()`` call
so downstream consumers (Mission Analyzer, dashboard, API) don't need to
know about the individual models.

.. code-block:: python

    core = PHMCore.load()
    result = core.predict(residual_z={"egt": 1.2, ...}, engine_hours=500.0)
    # result = {
    #     "anomaly": False,
    #     "anomaly_score": 0.12,
    #     "degradation_stage": "healthy",
    #     "stage_confidence": 0.97,
    #     "health_index": 97.0,
    #     "rul_hours": 342.0,
    #     "rul_confidence_interval": [328.0, 356.0],
    # }
"""

from __future__ import annotations

from pathlib import Path

from ml.anomaly_detector import AnomalyDetector
from ml.fault_classifier import FaultClassifier
from ml.rul_estimator import RULEstimator
from ml import health_index


class PHMCore:
    """Unified PHM inference engine.

    Loads the three trained models and the deterministic health-index
    function, and exposes a single ``predict()`` call.

    Parameters
    ----------
    anomaly_detector : AnomalyDetector
    fault_classifier : FaultClassifier
    rul_estimator : RULEstimator
    """

    def __init__(
        self,
        anomaly_detector: AnomalyDetector,
        fault_classifier: FaultClassifier,
        rul_estimator: RULEstimator,
    ):
        self.anomaly_detector = anomaly_detector
        self.fault_classifier = fault_classifier
        self.rul_estimator = rul_estimator

    @classmethod
    def load(cls, artifacts_dir: str | Path = "ml/artifacts") -> "PHMCore":
        """Load all sub-models from the artifacts directory."""
        return cls(
            anomaly_detector=AnomalyDetector.load(artifacts_dir),
            fault_classifier=FaultClassifier.load(artifacts_dir),
            rul_estimator=RULEstimator.load(artifacts_dir),
        )

    def predict(self, residual_z: dict, engine_hours: float) -> dict:
        """Run the full PHM pipeline on a single sample.

        Parameters
        ----------
        residual_z : dict
            Per-sensor z-scores (keys: egt, cht, oil_pressure, …).
        engine_hours : float
            Current engine hours.

        Returns
        -------
        dict with keys:
            anomaly, anomaly_score, degradation_stage, stage_confidence,
            health_index, rul_hours, rul_confidence_interval.
        """
        # 1. Anomaly detection
        anomaly_result = self.anomaly_detector.predict(residual_z)

        # 2. Fault / degradation classification
        fault_result = self.fault_classifier.predict(residual_z, engine_hours)

        # 3. RUL estimation
        rul_result = self.rul_estimator.predict(residual_z, engine_hours)

        # 4. Health Index (deterministic)
        hi = health_index.compute(
            stage=fault_result["stage"],
            anomaly_score=anomaly_result["anomaly_score"],
            stage_confidence=fault_result["confidence"],
        )

        return {
            "anomaly": anomaly_result["is_anomalous"],
            "anomaly_score": anomaly_result["anomaly_score"],
            "degradation_stage": fault_result["stage"],
            "stage_confidence": fault_result["confidence"],
            "health_index": hi,
            "rul_hours": rul_result["rul_hours"],
            "rul_confidence_interval": [
                rul_result["rul_lower"],
                rul_result["rul_upper"],
            ],
        }
