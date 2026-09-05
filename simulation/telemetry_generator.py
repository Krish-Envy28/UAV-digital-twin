"""
Synthetic Piston-Engine Telemetry Generator
============================================

Generates realistic UAV piston-engine telemetry data with configurable
degradation trajectories. Produces JSONL files matching the Phase 1A
telemetry schema.

Design decisions for Phase 1B+ compatibility:
  - Every sample carries `degradation_stage` and `engine_hours` so downstream
    classifiers / health-index models can consume them directly.
  - The `TelemetryGenerator` class is re-usable as a real-time replay iterator
    (`get_next_sample()`) for the streaming dashboard in Phase 3/4.
  - All random seeds are controllable for reproducibility.
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TWIN_INPUTS = ["rpm", "throttle", "map", "altitude", "ambient_temp"]
TWIN_OUTPUTS = ["egt", "cht", "oil_pressure", "oil_temp", "vibration", "fuel_flow"]
ALL_FIELDS = (
    ["timestamp"]
    + TWIN_INPUTS
    + TWIN_OUTPUTS
    + ["engine_hours", "degradation_stage"]
)

DEGRADATION_STAGES = [
    "healthy",
    "early_deviation",
    "incipient_degradation",
    "progressive_degradation",
    "critical",
]

# Degradation stage boundaries (fraction of total engine-hours in a trajectory run)
STAGE_BOUNDARIES = [0.0, 0.20, 0.40, 0.60, 0.80, 1.0]


# ---------------------------------------------------------------------------
# Mission profile helpers
# ---------------------------------------------------------------------------

@dataclass
class MissionPhase:
    """Describes one segment of a flight mission."""

    name: str
    duration_s: int  # seconds
    throttle_start: float  # %
    throttle_end: float  # %
    altitude_start: float  # ft
    altitude_end: float  # ft


def default_mission_profile() -> List[MissionPhase]:
    """A typical MALE-UAV sortie: ground-run → climb → cruise → maneuver → descent → landing."""
    return [
        MissionPhase("ground_run", 30, 30.0, 85.0, 0.0, 0.0),
        MissionPhase("climb", 120, 85.0, 75.0, 0.0, 8000.0),
        MissionPhase("cruise_1", 300, 65.0, 65.0, 8000.0, 8000.0),
        MissionPhase("maneuver_climb", 60, 80.0, 80.0, 8000.0, 10000.0),
        MissionPhase("cruise_high", 200, 60.0, 60.0, 10000.0, 10000.0),
        MissionPhase("maneuver_descend", 60, 50.0, 55.0, 10000.0, 6000.0),
        MissionPhase("cruise_2", 200, 62.0, 62.0, 6000.0, 6000.0),
        MissionPhase("descent", 90, 40.0, 30.0, 6000.0, 500.0),
        MissionPhase("landing", 40, 30.0, 20.0, 500.0, 0.0),
    ]


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b at fraction t ∈ [0, 1]."""
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Physics-inspired sensor model
# ---------------------------------------------------------------------------

class EnginePhysicsModel:
    """
    Simplified physics relationships for a horizontally-opposed piston engine.
    All formulas produce plausible magnitudes; they are *not* a validated
    thermodynamic model — they exist to give the Digital Twin something
    realistic to learn.
    """

    # --- Twin inputs (derived from mission profile) ---

    @staticmethod
    def compute_rpm(throttle: float, altitude: float) -> float:
        """RPM roughly proportional to throttle, with ~5 % drop at 10 000 ft."""
        base_rpm = 800 + throttle * 42.0  # idle ~800, max ~5000
        alt_factor = 1.0 - 0.05 * (altitude / 10_000.0)
        return base_rpm * max(alt_factor, 0.80)

    @staticmethod
    def compute_map(rpm: float, throttle: float, altitude: float) -> float:
        """Manifold Absolute Pressure (kPa).  Sea-level ambient ~101 kPa."""
        ambient_p = 101.325 * math.exp(-altitude / 27_000.0)  # barometric approx
        return ambient_p * (0.3 + 0.007 * throttle) * (rpm / 5000.0) ** 0.2

    @staticmethod
    def compute_ambient_temp(altitude: float) -> float:
        """ISA lapse rate: −2 °C per 1 000 ft from 15 °C at sea level."""
        return 15.0 - 2.0 * (altitude / 1000.0)

    # --- Twin outputs (healthy baseline) ---

    @staticmethod
    def compute_egt(rpm: float, throttle: float, map_kpa: float) -> float:
        return 400.0 + 0.04 * rpm + 1.8 * throttle + 0.6 * map_kpa

    @staticmethod
    def compute_cht(rpm: float, throttle: float) -> float:
        return 100.0 + 0.008 * rpm + 0.8 * throttle

    @staticmethod
    def compute_oil_pressure(rpm: float, oil_temp: float) -> float:
        return 25.0 + 0.007 * rpm - 0.08 * (oil_temp - 80.0)

    @staticmethod
    def compute_oil_temp(rpm: float, throttle: float, ambient_temp: float) -> float:
        return ambient_temp + 30.0 + 0.006 * rpm + 0.35 * throttle

    @staticmethod
    def compute_vibration(rpm: float) -> float:
        return 0.15 + 0.00005 * rpm + 0.1 * abs(math.sin(rpm / 800.0))

    @staticmethod
    def compute_fuel_flow(rpm: float, throttle: float, map_kpa: float) -> float:
        return 2.0 + 0.001 * rpm + 0.08 * throttle + 0.02 * map_kpa


# ---------------------------------------------------------------------------
# Degradation model
# ---------------------------------------------------------------------------

@dataclass
class DegradationProfile:
    """
    Per-sensor maximum degradation offsets at the 'critical' stage.
    The actual offset at any point = severity * max_offset.
    severity ∈ [0, 1] maps linearly within the trajectory.

    Design note: stored as a dataclass so Phase 1B can subclass / extend
    with fault-specific profiles (e.g. bearing failure vs exhaust leak).
    """

    egt_offset: float = 55.0        # °C hotter exhaust
    cht_offset: float = 30.0        # °C hotter cylinder heads
    oil_pressure_offset: float = -18.0  # psi drop (negative = lower)
    oil_temp_offset: float = 25.0   # °C hotter oil
    vibration_mult: float = 2.5     # multiplicative increase
    fuel_flow_offset: float = 3.5   # L/h increase (less efficient)
    noise_growth: float = 2.0       # noise σ multiplier at critical


def _severity(engine_hours: float, max_hours: float) -> float:
    """Smooth severity curve: 0 at start, 1 at max_hours. Uses a cubic
    ramp so early hours stay near zero and late hours ramp steeply —
    mimicking real degradation kinetics."""
    t = min(max(engine_hours / max_hours, 0.0), 1.0)
    return t ** 2.5  # sub-linear early, steep late


def _stage_for_severity(severity: float) -> str:
    """Map severity ∈ [0, 1] to a degradation stage label."""
    if severity < 0.05:
        return "healthy"
    elif severity < 0.15:
        return "early_deviation"
    elif severity < 0.35:
        return "incipient_degradation"
    elif severity < 0.65:
        return "progressive_degradation"
    else:
        return "critical"


# ---------------------------------------------------------------------------
# Telemetry generator
# ---------------------------------------------------------------------------

class TelemetryGenerator:
    """
    Generates one engine run (a sequence of telemetry samples).

    Parameters
    ----------
    mission : list[MissionPhase] | None
        Flight profile. Defaults to `default_mission_profile()`.
    healthy_only : bool
        If True, no degradation is injected (used for training data).
    engine_hours_start : float
        Engine-hours at the start of the run.
    max_engine_hours : float
        Engine-hours at which severity reaches 1.0 (only relevant when
        `healthy_only=False`).
    degradation : DegradationProfile | None
        Custom degradation profile. Defaults to standard profile.
    seed : int | None
        Numpy / random seed for reproducibility.
    """

    def __init__(
        self,
        mission: Optional[List[MissionPhase]] = None,
        healthy_only: bool = True,
        engine_hours_start: float = 50.0,
        max_engine_hours: float = 1000.0,
        degradation: Optional[DegradationProfile] = None,
        seed: Optional[int] = None,
    ):
        self.mission = mission or default_mission_profile()
        self.healthy_only = healthy_only
        self.engine_hours_start = engine_hours_start
        self.max_engine_hours = max_engine_hours
        self.degradation = degradation or DegradationProfile()
        self.physics = EnginePhysicsModel()

        self._rng = np.random.default_rng(seed)

        # Total samples in the run
        self.total_samples = sum(p.duration_s for p in self.mission)

        # Pre-compute engine-hours increment per sample
        # For healthy runs, engine_hours stays in healthy range
        if self.healthy_only:
            self._hours_per_sample = 0.5 / self.total_samples  # ~0.5 h per run, stays healthy
        else:
            # Span from engine_hours_start to max_engine_hours
            self._hours_span = self.max_engine_hours - self.engine_hours_start
            self._hours_per_sample = self._hours_span / self.total_samples

    def _noise(self, sigma: float, severity: float = 0.0) -> float:
        """Gaussian noise with severity-dependent variance growth."""
        growth = 1.0 + severity * (self.degradation.noise_growth - 1.0)
        return float(self._rng.normal(0, sigma * growth))

    def generate(self) -> Iterator[dict]:
        """Yield one telemetry sample dict per timestep."""
        sample_idx = 0
        engine_hours = self.engine_hours_start

        for phase in self.mission:
            for t in range(phase.duration_s):
                frac = t / max(phase.duration_s - 1, 1)

                # --- Mission-profile driven inputs ---
                throttle = _lerp(phase.throttle_start, phase.throttle_end, frac)
                altitude = _lerp(phase.altitude_start, phase.altitude_end, frac)

                # --- Derived inputs ---
                rpm = self.physics.compute_rpm(throttle, altitude)
                map_kpa = self.physics.compute_map(rpm, throttle, altitude)
                ambient_temp = self.physics.compute_ambient_temp(altitude)

                # --- Severity & stage ---
                if self.healthy_only:
                    sev = 0.0
                    stage = "healthy"
                else:
                    sev = _severity(engine_hours, self.max_engine_hours)
                    stage = _stage_for_severity(sev)

                deg = self.degradation

                # --- Healthy baseline outputs + degradation + noise ---
                egt_base = self.physics.compute_egt(rpm, throttle, map_kpa)
                egt = egt_base + sev * deg.egt_offset + self._noise(3.0, sev)

                cht_base = self.physics.compute_cht(rpm, throttle)
                cht = cht_base + sev * deg.cht_offset + self._noise(2.0, sev)

                oil_temp_base = self.physics.compute_oil_temp(rpm, throttle, ambient_temp)
                oil_temp = oil_temp_base + sev * deg.oil_temp_offset + self._noise(1.5, sev)

                oil_pres_base = self.physics.compute_oil_pressure(rpm, oil_temp_base)
                oil_pressure = oil_pres_base + sev * deg.oil_pressure_offset + self._noise(1.0, sev)

                vib_base = self.physics.compute_vibration(rpm)
                vibration = vib_base * (1.0 + sev * (deg.vibration_mult - 1.0)) + self._noise(0.03, sev)
                vibration = max(vibration, 0.01)  # vibration can't be negative

                fuel_base = self.physics.compute_fuel_flow(rpm, throttle, map_kpa)
                fuel_flow = fuel_base + sev * deg.fuel_flow_offset + self._noise(0.3, sev)

                sample = {
                    "timestamp": round(float(sample_idx), 1),
                    "rpm": round(rpm + self._noise(15.0, sev), 1),
                    "throttle": round(throttle + self._noise(0.3, sev), 1),
                    "map": round(map_kpa + self._noise(0.5, sev), 2),
                    "altitude": round(altitude + self._noise(5.0, sev), 1),
                    "ambient_temp": round(ambient_temp + self._noise(0.2, sev), 1),
                    "egt": round(egt, 1),
                    "cht": round(cht, 1),
                    "oil_pressure": round(oil_pressure, 1),
                    "oil_temp": round(oil_temp, 1),
                    "vibration": round(vibration, 3),
                    "fuel_flow": round(fuel_flow, 2),
                    "engine_hours": round(engine_hours, 1),
                    "degradation_stage": stage,
                }
                yield sample

                sample_idx += 1
                engine_hours += self._hours_per_sample

    def get_next_sample(self) -> dict:
        """Pull interface for replay / streaming (Phase 3/4 compatible).
        Returns next sample from the internal iterator. Raises StopIteration
        when the run is exhausted."""
        if not hasattr(self, "_iter"):
            self._iter = self.generate()
        return next(self._iter)


# ---------------------------------------------------------------------------
# Dataset generation (batch)
# ---------------------------------------------------------------------------

def generate_dataset(
    output_dir: str | Path = "data",
    n_healthy: int = 5,
    n_trajectory: int = 3,
    base_seed: int = 42,
) -> dict:
    """
    Generate the full Phase 1A dataset.

    Returns
    -------
    dict with keys:
        healthy_files : list[str]   — paths to healthy-only JSONL files
        trajectory_files : list[str] — paths to full-trajectory JSONL files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    healthy_files = []
    trajectory_files = []

    # --- Healthy runs (for Digital Twin training) ---
    for i in range(n_healthy):
        fname = output_dir / f"healthy_run_{i + 1:02d}.jsonl"
        gen = TelemetryGenerator(
            healthy_only=True,
            engine_hours_start=float(20 + i * 10),  # vary start slightly
            seed=base_seed + i,
        )
        with open(fname, "w") as f:
            for sample in gen.generate():
                f.write(json.dumps(sample) + "\n")
        healthy_files.append(str(fname))
        print(f"  [OK] Generated {fname}  ({gen.total_samples} samples)")

    # --- Full-trajectory runs (healthy → critical, for testing) ---
    for i in range(n_trajectory):
        fname = output_dir / f"trajectory_run_{i + 1:02d}.jsonl"
        gen = TelemetryGenerator(
            healthy_only=False,
            engine_hours_start=50.0,
            max_engine_hours=1000.0,
            seed=base_seed + 100 + i,
        )
        with open(fname, "w") as f:
            for sample in gen.generate():
                f.write(json.dumps(sample) + "\n")
        trajectory_files.append(str(fname))
        print(f"  [OK] Generated {fname}  ({gen.total_samples} samples)")

    return {"healthy_files": healthy_files, "trajectory_files": trajectory_files}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating Phase 1A synthetic telemetry dataset...\n")
    result = generate_dataset()
    print(f"\nDone.  Healthy: {len(result['healthy_files'])},  "
          f"Trajectory: {len(result['trajectory_files'])}")
