"""Unit tests for the Digital Twin model."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from simulation.telemetry_generator import TelemetryGenerator, generate_dataset
from ml.digital_twin import DigitalTwin, TWIN_INPUTS, TWIN_OUTPUTS


@pytest.fixture(scope="module")
def trained_twin(tmp_path_factory):
    """Train a small twin on 2 healthy runs for testing."""
    data_dir = tmp_path_factory.mktemp("data")
    artifacts_dir = tmp_path_factory.mktemp("artifacts")

    result = generate_dataset(output_dir=data_dir, n_healthy=2, n_trajectory=0, base_seed=77)

    twin = DigitalTwin()
    twin.train(result["healthy_files"])
    twin.save(artifacts_dir)

    return twin, artifacts_dir


class TestDigitalTwinPredict:
    """Test the predict interface."""

    def test_predict_returns_all_outputs(self, trained_twin):
        twin, _ = trained_twin
        sample = {
            "rpm": 4000, "throttle": 60.0, "map": 75.0,
            "altitude": 8000, "ambient_temp": -1.0,
        }
        result = twin.predict(sample)
        for sensor in TWIN_OUTPUTS:
            assert sensor in result, f"Missing output: {sensor}"
            assert isinstance(result[sensor], float)

    def test_predict_values_are_plausible(self, trained_twin):
        twin, _ = trained_twin
        sample = {
            "rpm": 4000, "throttle": 60.0, "map": 75.0,
            "altitude": 8000, "ambient_temp": -1.0,
        }
        result = twin.predict(sample)
        # EGT should be in a reasonable range for these conditions
        assert 400 < result["egt"] < 900
        assert 80 < result["cht"] < 300
        assert 10 < result["oil_pressure"] < 100
        assert 0 < result["oil_temp"] < 160
        assert result["vibration"] > 0
        assert result["fuel_flow"] > 0

    def test_predict_is_condition_aware(self, trained_twin):
        """Different operating conditions should produce different predictions."""
        twin, _ = trained_twin
        low_load = {"rpm": 2000, "throttle": 30.0, "map": 40.0,
                     "altitude": 2000, "ambient_temp": 10.0}
        high_load = {"rpm": 4500, "throttle": 85.0, "map": 90.0,
                      "altitude": 8000, "ambient_temp": -5.0}

        pred_low = twin.predict(low_load)
        pred_high = twin.predict(high_load)

        # EGT should be higher at high load
        assert pred_high["egt"] > pred_low["egt"]
        # Fuel flow should be higher at high load
        assert pred_high["fuel_flow"] > pred_low["fuel_flow"]


class TestDigitalTwinPersistence:
    """Test save/load roundtrip."""

    def test_load_produces_same_predictions(self, trained_twin):
        twin_original, artifacts_dir = trained_twin
        twin_loaded = DigitalTwin.load(artifacts_dir)

        sample = {
            "rpm": 3500, "throttle": 55.0, "map": 68.0,
            "altitude": 6000, "ambient_temp": 3.0,
        }
        pred_original = twin_original.predict(sample)
        pred_loaded = twin_loaded.predict(sample)

        for sensor in TWIN_OUTPUTS:
            assert abs(pred_original[sensor] - pred_loaded[sensor]) < 1e-6


class TestStdHealthy:
    """Test that std_healthy is computed and reasonable."""

    def test_std_healthy_has_all_sensors(self, trained_twin):
        twin, _ = trained_twin
        for sensor in TWIN_OUTPUTS:
            assert sensor in twin.std_healthy
            assert twin.std_healthy[sensor] > 0
