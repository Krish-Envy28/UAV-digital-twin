"""
PHM Unit Tests
===============

Tests the interface contracts for each Phase 1B module:
  - Correct output keys and types
  - Value ranges (scores in [0,1], health index in [0,100], RUL >= 0)
  - Health index formula sanity
"""

import pytest
from ml.anomaly_detector import AnomalyDetector
from ml.fault_classifier import FaultClassifier, DEGRADATION_STAGES
from ml.rul_estimator import RULEstimator
from ml.health_index import compute as compute_health_index
from ml.phm_core import PHMCore


# ---- Fixtures ----

@pytest.fixture(scope="module")
def anomaly_detector():
    return AnomalyDetector.load()


@pytest.fixture(scope="module")
def fault_classifier():
    return FaultClassifier.load()


@pytest.fixture(scope="module")
def rul_estimator():
    return RULEstimator.load()


@pytest.fixture(scope="module")
def phm_core():
    return PHMCore.load()


# Sample residual_z inputs
HEALTHY_RZ = {"egt": 0.3, "cht": 0.2, "oil_pressure": 0.1,
              "oil_temp": 0.2, "vibration": 0.1, "fuel_flow": 0.15}

CRITICAL_RZ = {"egt": 18.0, "cht": 12.0, "oil_pressure": -15.0,
               "oil_temp": 14.0, "vibration": 10.0, "fuel_flow": 8.0}


# ---- Anomaly Detector Tests ----

class TestAnomalyDetector:
    def test_output_keys(self, anomaly_detector):
        result = anomaly_detector.predict(HEALTHY_RZ)
        assert "is_anomalous" in result
        assert "anomaly_score" in result

    def test_output_types(self, anomaly_detector):
        result = anomaly_detector.predict(HEALTHY_RZ)
        assert isinstance(result["is_anomalous"], bool)
        assert isinstance(result["anomaly_score"], float)

    def test_score_range(self, anomaly_detector):
        result = anomaly_detector.predict(HEALTHY_RZ)
        assert 0.0 <= result["anomaly_score"] <= 1.0

    def test_healthy_not_anomalous(self, anomaly_detector):
        result = anomaly_detector.predict(HEALTHY_RZ)
        assert result["is_anomalous"] is False

    def test_critical_is_anomalous(self, anomaly_detector):
        result = anomaly_detector.predict(CRITICAL_RZ)
        assert result["is_anomalous"] is True


# ---- Fault Classifier Tests ----

class TestFaultClassifier:
    def test_output_keys(self, fault_classifier):
        result = fault_classifier.predict(HEALTHY_RZ, engine_hours=100.0)
        assert "stage" in result
        assert "confidence" in result
        assert "class_probabilities" in result

    def test_stage_is_valid(self, fault_classifier):
        result = fault_classifier.predict(HEALTHY_RZ, engine_hours=100.0)
        assert result["stage"] in DEGRADATION_STAGES

    def test_confidence_range(self, fault_classifier):
        result = fault_classifier.predict(HEALTHY_RZ, engine_hours=100.0)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_class_probabilities_sum_to_one(self, fault_classifier):
        result = fault_classifier.predict(HEALTHY_RZ, engine_hours=100.0)
        total = sum(result["class_probabilities"].values())
        assert abs(total - 1.0) < 0.01

    def test_healthy_classified_as_healthy(self, fault_classifier):
        result = fault_classifier.predict(HEALTHY_RZ, engine_hours=100.0)
        assert result["stage"] == "healthy"

    def test_critical_classified_as_critical(self, fault_classifier):
        result = fault_classifier.predict(CRITICAL_RZ, engine_hours=900.0)
        assert result["stage"] == "critical"


# ---- RUL Estimator Tests ----

class TestRULEstimator:
    def test_output_keys(self, rul_estimator):
        result = rul_estimator.predict(HEALTHY_RZ, engine_hours=100.0)
        assert "rul_hours" in result
        assert "rul_lower" in result
        assert "rul_upper" in result

    def test_rul_non_negative(self, rul_estimator):
        result = rul_estimator.predict(HEALTHY_RZ, engine_hours=100.0)
        assert result["rul_hours"] >= 0.0
        assert result["rul_lower"] >= 0.0
        assert result["rul_upper"] >= 0.0

    def test_interval_ordering(self, rul_estimator):
        result = rul_estimator.predict(HEALTHY_RZ, engine_hours=100.0)
        assert result["rul_lower"] <= result["rul_hours"] <= result["rul_upper"]

    def test_healthy_has_more_rul_than_critical(self, rul_estimator):
        healthy = rul_estimator.predict(HEALTHY_RZ, engine_hours=100.0)
        critical = rul_estimator.predict(CRITICAL_RZ, engine_hours=900.0)
        assert healthy["rul_hours"] > critical["rul_hours"]


# ---- Health Index Tests ----

class TestHealthIndex:
    def test_healthy_near_100(self):
        hi = compute_health_index("healthy", 0.0, 1.0)
        assert hi >= 90.0

    def test_critical_near_0(self):
        hi = compute_health_index("critical", 1.0, 1.0)
        assert hi <= 10.0

    def test_clamped_to_range(self):
        hi = compute_health_index("healthy", 0.0, 1.0)
        assert 0.0 <= hi <= 100.0
        hi = compute_health_index("critical", 1.0, 0.5)
        assert 0.0 <= hi <= 100.0

    def test_anomaly_penalises(self):
        hi_clean = compute_health_index("healthy", 0.0, 1.0)
        hi_dirty = compute_health_index("healthy", 1.0, 1.0)
        assert hi_dirty < hi_clean

    def test_low_confidence_reduces(self):
        hi_high = compute_health_index("healthy", 0.0, 1.0)
        hi_low = compute_health_index("healthy", 0.0, 0.5)
        assert hi_low < hi_high


# ---- PHM Core Integration Tests ----

class TestPHMCore:
    def test_output_keys(self, phm_core):
        result = phm_core.predict(HEALTHY_RZ, engine_hours=100.0)
        expected_keys = {
            "anomaly", "anomaly_score", "degradation_stage",
            "stage_confidence", "health_index", "rul_hours",
            "rul_confidence_interval",
        }
        assert set(result.keys()) == expected_keys

    def test_confidence_interval_is_list(self, phm_core):
        result = phm_core.predict(HEALTHY_RZ, engine_hours=100.0)
        assert isinstance(result["rul_confidence_interval"], list)
        assert len(result["rul_confidence_interval"]) == 2

    def test_healthy_scenario(self, phm_core):
        result = phm_core.predict(HEALTHY_RZ, engine_hours=100.0)
        assert result["anomaly"] is False
        assert result["degradation_stage"] == "healthy"
        assert result["health_index"] >= 80.0
        assert result["rul_hours"] > 100.0

    def test_critical_scenario(self, phm_core):
        result = phm_core.predict(CRITICAL_RZ, engine_hours=900.0)
        assert result["anomaly"] is True
        assert result["degradation_stage"] == "critical"
        assert result["health_index"] <= 20.0
        assert result["rul_hours"] < 50.0
