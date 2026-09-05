"""Unit tests for the synthetic telemetry generator."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from simulation.telemetry_generator import (
    ALL_FIELDS,
    DEGRADATION_STAGES,
    TelemetryGenerator,
    generate_dataset,
)


class TestTelemetryGeneratorSchema:
    """Verify output samples match the Phase 1A telemetry schema."""

    def test_sample_has_all_fields(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        sample = next(gen.generate())
        for field in ALL_FIELDS:
            assert field in sample, f"Missing field: {field}"

    def test_sample_values_are_numeric(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        sample = next(gen.generate())
        for field in ALL_FIELDS:
            if field == "degradation_stage":
                assert isinstance(sample[field], str)
            else:
                assert isinstance(sample[field], (int, float)), \
                    f"{field} should be numeric, got {type(sample[field])}"


class TestHealthyRuns:
    """Verify healthy-only runs have correct degradation labeling."""

    def test_all_samples_labeled_healthy(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        for sample in gen.generate():
            assert sample["degradation_stage"] == "healthy"

    def test_total_sample_count(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        samples = list(gen.generate())
        assert len(samples) == gen.total_samples


class TestTrajectoryRuns:
    """Verify full-trajectory runs progress through all degradation stages."""

    def test_passes_through_all_stages(self):
        gen = TelemetryGenerator(healthy_only=False, seed=0)
        stages_seen = set()
        for sample in gen.generate():
            stages_seen.add(sample["degradation_stage"])
        for stage in DEGRADATION_STAGES:
            assert stage in stages_seen, f"Missing stage: {stage}"

    def test_engine_hours_increase(self):
        gen = TelemetryGenerator(healthy_only=False, seed=0)
        samples = list(gen.generate())
        hours = [s["engine_hours"] for s in samples]
        assert hours == sorted(hours), "engine_hours should be monotonically increasing"


class TestSensorRanges:
    """Verify sensor values are in physically plausible ranges."""

    def test_healthy_sensor_ranges(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        for sample in gen.generate():
            assert 500 < sample["rpm"] < 6000
            assert 0 < sample["throttle"] < 100
            assert 0 < sample["map"] < 120
            assert -500 < sample["altitude"] < 15000
            assert -60 < sample["ambient_temp"] < 50
            assert 300 < sample["egt"] < 1000
            assert 50 < sample["cht"] < 350
            assert 0 < sample["oil_pressure"] < 120
            assert -10 < sample["oil_temp"] < 180
            assert sample["vibration"] > 0
            assert sample["fuel_flow"] > 0


class TestGetNextSample:
    """Test the replay/streaming interface for Phase 3/4 compatibility."""

    def test_get_next_sample_returns_samples(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        s1 = gen.get_next_sample()
        s2 = gen.get_next_sample()
        assert s1["timestamp"] != s2["timestamp"]

    def test_get_next_sample_exhausts(self):
        gen = TelemetryGenerator(healthy_only=True, seed=0)
        count = 0
        with pytest.raises(StopIteration):
            while True:
                gen.get_next_sample()
                count += 1
        assert count == gen.total_samples


class TestGenerateDataset:
    """Test batch dataset generation."""

    def test_generates_correct_file_counts(self, tmp_path):
        result = generate_dataset(
            output_dir=tmp_path, n_healthy=2, n_trajectory=1, base_seed=99
        )
        assert len(result["healthy_files"]) == 2
        assert len(result["trajectory_files"]) == 1
        for fpath in result["healthy_files"] + result["trajectory_files"]:
            assert os.path.exists(fpath)

    def test_jsonl_is_valid(self, tmp_path):
        result = generate_dataset(
            output_dir=tmp_path, n_healthy=1, n_trajectory=1, base_seed=99
        )
        for fpath in result["healthy_files"] + result["trajectory_files"]:
            with open(fpath) as f:
                for line in f:
                    record = json.loads(line)  # must not raise
                    assert "timestamp" in record
