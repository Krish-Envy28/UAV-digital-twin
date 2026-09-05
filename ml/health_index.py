"""
Health Index
=============

Deterministic combination function — **not** a trained ML model.

Produces a single 0–100 score from the anomaly detector's score and the
fault classifier's output, following the formula in Phase 1B spec section 5:

.. code-block:: text

    stage_base = {healthy: 100, early_deviation: 80, incipient_degradation: 55,
                  progressive_degradation: 30, critical: 5}[predicted_stage]

    health_index = clamp(stage_base - anomaly_score * 15, 0, 100) * stage_confidence
    # clamp final result to [0, 100]

This keeps the index smooth within a stage (the anomaly_score modulates it)
while still being anchored to the classifier's stage prediction.
"""

from __future__ import annotations

# Stage → base score mapping (from spec)
STAGE_BASE_SCORES = {
    "healthy": 100,
    "early_deviation": 80,
    "incipient_degradation": 55,
    "progressive_degradation": 30,
    "critical": 5,
}


def compute(
    stage: str,
    anomaly_score: float,
    stage_confidence: float,
) -> float:
    """Compute the Health Index (0–100).

    Parameters
    ----------
    stage : str
        Predicted degradation stage from the fault classifier.
    anomaly_score : float
        Normalised anomaly score (0 = normal, 1 = extreme) from the
        anomaly detector.
    stage_confidence : float
        Confidence of the fault classifier's stage prediction (0–1).

    Returns
    -------
    float
        Health Index, clamped to [0, 100].
    """
    base = STAGE_BASE_SCORES.get(stage, 50)

    # Penalise high anomaly within a stage
    hi = max(min(base - anomaly_score * 15, 100), 0)

    # Scale by classifier confidence
    hi = hi * stage_confidence

    # Final clamp
    return round(max(min(hi, 100.0), 0.0), 2)
