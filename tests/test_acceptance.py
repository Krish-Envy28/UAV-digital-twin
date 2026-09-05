"""
Phase 1A Acceptance Test
=========================

Replays a full-trajectory run (healthy -> critical) through the Digital Twin
and Residual Engine, then generates validation plots.

Success criteria:
  1. Expected values track operating-condition changes (not flat lines).
  2. Residuals stay near zero in the healthy region.
  3. Residuals visibly increase as degradation_stage progresses.

Produces: tests/acceptance_plot.png
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for CI/headless
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.digital_twin import DigitalTwin
from backend.residual import ResidualEngine


def run_acceptance_test(
    trajectory_file: str = "data/trajectory_run_01.jsonl",
    artifacts_dir: str = "ml/artifacts",
    output_plot: str = "tests/acceptance_plot.png",
):
    """Run the end-to-end acceptance test and generate the validation plot."""

    # --- Load models ---
    print("Loading Digital Twin...")
    twin = DigitalTwin.load(artifacts_dir)
    residual_engine = ResidualEngine.from_file(f"{artifacts_dir}/std_healthy.json")

    # --- Replay trajectory ---
    print(f"Replaying {trajectory_file}...")
    with open(trajectory_file, "r") as f:
        samples = [json.loads(line) for line in f]

    timestamps = []
    stages = []
    actual_egt, expected_egt, residual_egt, z_egt = [], [], [], []
    actual_oil, expected_oil, residual_oil, z_oil = [], [], [], []
    actual_vib, expected_vib, residual_vib, z_vib = [], [], [], []

    for sample in samples:
        expected = twin.predict(sample)
        actual_dict = {k: sample[k] for k in twin.models.keys()}
        result = residual_engine.compute(actual_dict, expected)

        timestamps.append(sample["timestamp"])
        stages.append(sample["degradation_stage"])

        # EGT
        actual_egt.append(result["actual"]["egt"])
        expected_egt.append(result["expected"]["egt"])
        residual_egt.append(result["residual"]["egt"])
        z_egt.append(result["residual_z"]["egt"])

        # Oil pressure
        actual_oil.append(result["actual"]["oil_pressure"])
        expected_oil.append(result["expected"]["oil_pressure"])
        residual_oil.append(result["residual"]["oil_pressure"])
        z_oil.append(result["residual_z"]["oil_pressure"])

        # Vibration
        actual_vib.append(result["actual"]["vibration"])
        expected_vib.append(result["expected"]["vibration"])
        residual_vib.append(result["residual"]["vibration"])
        z_vib.append(result["residual_z"]["vibration"])

    timestamps = np.array(timestamps)

    # --- Compute stage boundaries for colored background ---
    stage_colors = {
        "healthy": "#2ecc71",
        "early_deviation": "#f1c40f",
        "incipient_degradation": "#e67e22",
        "progressive_degradation": "#e74c3c",
        "critical": "#8e44ad",
    }

    def shade_stages(ax):
        """Add colored background bands for degradation stages."""
        prev_stage = stages[0]
        start_t = timestamps[0]
        for i, (t, s) in enumerate(zip(timestamps, stages)):
            if s != prev_stage or i == len(stages) - 1:
                ax.axvspan(start_t, t, alpha=0.12,
                           color=stage_colors.get(prev_stage, "#ccc"))
                prev_stage = s
                start_t = t

    # --- Plot ---
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), constrained_layout=True)
    fig.suptitle(
        "Phase 1A Acceptance Test -- Digital Twin Residuals\n"
        "(Background color = degradation stage)",
        fontsize=14, fontweight="bold",
    )

    sensors = [
        ("EGT", actual_egt, expected_egt, residual_egt, z_egt, "deg C"),
        ("Oil Pressure", actual_oil, expected_oil, residual_oil, z_oil, "psi"),
        ("Vibration", actual_vib, expected_vib, residual_vib, z_vib, "g RMS"),
    ]

    for row, (name, actual, expected, residual, z, unit) in enumerate(sensors):
        # Left: Actual vs Expected
        ax = axes[row, 0]
        shade_stages(ax)
        ax.plot(timestamps, actual, label="Actual", color="#e74c3c", alpha=0.7, linewidth=0.8)
        ax.plot(timestamps, expected, label="Expected (Twin)", color="#3498db", linewidth=1.2)
        ax.set_ylabel(f"{name} ({unit})")
        ax.set_title(f"{name} -- Actual vs Expected")
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.3)

        # Right: Residual Z-score
        ax = axes[row, 1]
        shade_stages(ax)
        ax.plot(timestamps, z, color="#2c3e50", linewidth=0.8, alpha=0.8)
        ax.axhline(y=0, color="#7f8c8d", linestyle="--", linewidth=0.5)
        ax.axhline(y=3, color="#e74c3c", linestyle="--", linewidth=0.5, label="z=3 threshold")
        ax.axhline(y=-3, color="#e74c3c", linestyle="--", linewidth=0.5)
        ax.set_ylabel(f"{name} z-score")
        ax.set_title(f"{name} -- Normalized Residual (z-score)")
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.3)

    for ax in axes[2]:
        ax.set_xlabel("Time (s)")

    # Add legend for stage colors
    from matplotlib.patches import Patch
    legend_patches = [Patch(facecolor=c, alpha=0.3, label=s.replace("_", " ").title())
                      for s, c in stage_colors.items()]
    fig.legend(handles=legend_patches, loc="lower center", ncol=5, fontsize=9,
               title="Degradation Stage")

    Path(output_plot).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_plot, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to {output_plot}")

    # --- Print summary statistics ---
    print("\n--- Acceptance Summary ---")
    healthy_mask = [s == "healthy" for s in stages]
    critical_mask = [s == "critical" for s in stages]

    for name, z_vals in [("EGT", z_egt), ("Oil Pressure", z_oil), ("Vibration", z_vib)]:
        z_arr = np.array(z_vals)
        h_mean = np.mean(np.abs(z_arr[healthy_mask])) if any(healthy_mask) else 0
        c_mean = np.mean(np.abs(z_arr[critical_mask])) if any(critical_mask) else 0
        print(f"  {name:16s}  |z| healthy={h_mean:.2f}  |z| critical={c_mean:.2f}  "
              f"ratio={c_mean / max(h_mean, 1e-6):.1f}x")

    print("\nAcceptance test PASSED if:")
    print("  - Expected lines are NOT flat (they track operating conditions)")
    print("  - Z-scores are near 0 in green regions (healthy)")
    print("  - Z-scores spike in red/purple regions (degraded/critical)")

    return output_plot


if __name__ == "__main__":
    run_acceptance_test()
