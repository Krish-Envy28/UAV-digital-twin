"""Unit tests for the Residual Engine."""

import pytest

from backend.residual import ResidualEngine, TWIN_OUTPUTS


@pytest.fixture
def engine():
    """Create a ResidualEngine with known std values."""
    std_healthy = {
        "egt": 2.0,
        "cht": 1.5,
        "oil_pressure": 0.8,
        "oil_temp": 1.0,
        "vibration": 0.02,
        "fuel_flow": 0.2,
    }
    return ResidualEngine(std_healthy)


class TestResidualCompute:
    """Test the single-sample compute() interface."""

    def test_output_has_required_keys(self, engine):
        actual = {"egt": 710.0, "cht": 170.0, "oil_pressure": 55.0,
                  "oil_temp": 90.0, "vibration": 0.4, "fuel_flow": 12.0}
        expected = {"egt": 700.0, "cht": 165.0, "oil_pressure": 57.0,
                    "oil_temp": 88.0, "vibration": 0.35, "fuel_flow": 11.5}

        result = engine.compute(actual, expected)

        assert "actual" in result
        assert "expected" in result
        assert "residual" in result
        assert "residual_z" in result

    def test_residual_is_actual_minus_expected(self, engine):
        actual = {"egt": 710.0, "cht": 170.0, "oil_pressure": 55.0,
                  "oil_temp": 90.0, "vibration": 0.4, "fuel_flow": 12.0}
        expected = {"egt": 700.0, "cht": 165.0, "oil_pressure": 57.0,
                    "oil_temp": 88.0, "vibration": 0.35, "fuel_flow": 11.5}

        result = engine.compute(actual, expected)

        for sensor in TWIN_OUTPUTS:
            expected_residual = actual[sensor] - expected[sensor]
            assert abs(result["residual"][sensor] - expected_residual) < 1e-3

    def test_residual_z_is_normalized(self, engine):
        actual = {"egt": 710.0, "cht": 170.0, "oil_pressure": 55.0,
                  "oil_temp": 90.0, "vibration": 0.4, "fuel_flow": 12.0}
        expected = {"egt": 700.0, "cht": 165.0, "oil_pressure": 57.0,
                    "oil_temp": 88.0, "vibration": 0.35, "fuel_flow": 11.5}

        result = engine.compute(actual, expected)

        for sensor in TWIN_OUTPUTS:
            raw = actual[sensor] - expected[sensor]
            expected_z = raw / engine.std_healthy[sensor]
            assert abs(result["residual_z"][sensor] - expected_z) < 1e-3

    def test_zero_residual_when_perfect_match(self, engine):
        values = {"egt": 700.0, "cht": 165.0, "oil_pressure": 57.0,
                  "oil_temp": 88.0, "vibration": 0.35, "fuel_flow": 11.5}

        result = engine.compute(values, values)

        for sensor in TWIN_OUTPUTS:
            assert result["residual"][sensor] == 0.0
            assert result["residual_z"][sensor] == 0.0


class TestResidualEngineFromFile:
    """Test loading std_healthy from a JSON file."""

    def test_from_file_loads_correctly(self, tmp_path):
        import json
        std = {"egt": 2.0, "cht": 1.5, "oil_pressure": 0.8,
               "oil_temp": 1.0, "vibration": 0.02, "fuel_flow": 0.2}
        fpath = tmp_path / "std_healthy.json"
        with open(fpath, "w") as f:
            json.dump(std, f)

        engine = ResidualEngine.from_file(fpath)
        for sensor in TWIN_OUTPUTS:
            assert engine.std_healthy[sensor] == std[sensor]
