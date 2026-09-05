"""
Phase 1B Acceptance Test
=========================

Replays one full-trajectory run through the entire pipeline:

    telemetry -> digital_twin -> residual -> phm_core

and produces a 3-panel plot showing:
  1. Health Index over time (should trend downward)
  2. RUL (hours) with 80 % confidence band (should trend toward 0)
  3. Predicted vs ground-truth degradation stage

This is the Phase 1B proof point:
  **"Residual -> Health / Degradation / RUL works."**
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # non-interactive backend (no window needed)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from ml.digital_twin import DigitalTwin
from backend.residual import ResidualEngine
from ml.phm_core import PHMCore

# ---- Degradation stage colours / ordering ----

STAGE_ORDER = [
    "healthy",
    "early_deviation",
    "incipient_degradation",
    "progressive_degradation",
    "critical",
]
STAGE_COLORS = {
    "healthy": "#2ecc71",
    "early_deviation": "#f1c40f",
    "incipient_degradation": "#e67e22",
    "progressive_degradation": "#e74c3c",
    "critical": "#8e44ad",
}
STAGE_NUM = {s: i for i, s in enumerate(STAGE_ORDER)}


def main():
    # ---- Load models ----
    print("Loading models...")
    twin = DigitalTwin.load()
    residual_engine = ResidualEngine.from_file()
    phm = PHMCore.load()

    # ---- Load trajectory run 1 ----
    run_path = Path("data/trajectory_run_01.jsonl")
    print(f"Replaying {run_path}...")
    with open(run_path) as f:
        samples = [json.loads(line) for line in f]

    # ---- Run full pipeline ----
    timestamps = []
    engine_hours_list = []
    gt_stages = []           # ground-truth
    pred_stages = []         # predicted
    health_indices = []
    rul_points = []
    rul_lowers = []
    rul_uppers = []
    anomaly_scores = []

    for i, sample in enumerate(samples):
        # Digital Twin -> expected values
        expected = twin.predict(sample)
        # Residual Engine -> residual_z
        res = residual_engine.compute(sample, expected)
        rz = res["residual_z"]
        eh = sample["engine_hours"]

        # PHM Core -> everything
        phm_result = phm.predict(rz, eh)

        timestamps.append(sample["timestamp"])
        engine_hours_list.append(eh)
        gt_stages.append(sample["degradation_stage"])
        pred_stages.append(phm_result["degradation_stage"])
        health_indices.append(phm_result["health_index"])
        rul_points.append(phm_result["rul_hours"])
        rul_lowers.append(phm_result["rul_confidence_interval"][0])
        rul_uppers.append(phm_result["rul_confidence_interval"][1])
        anomaly_scores.append(phm_result["anomaly_score"])

    engine_hours = np.array(engine_hours_list)

    # ---- Compute ground-truth RUL for reference ----
    # First critical at engine_hours ~842
    critical_hours_gt = next(
        eh for eh, st in zip(engine_hours_list, gt_stages) if st == "critical"
    )
    gt_rul = np.maximum(critical_hours_gt - engine_hours, 0)

    # ---- Stage accuracy ----
    correct = sum(1 for g, p in zip(gt_stages, pred_stages) if g == p)
    accuracy = correct / len(gt_stages) * 100
    print(f"Stage classification accuracy: {accuracy:.1f}%")

    # ================================================================
    # PLOT
    # ================================================================
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(
        "Phase 1B Acceptance - PHM Core End-to-End\n"
        f"(trajectory_run_01, stage accuracy: {accuracy:.1f}%)",
        fontsize=14, fontweight="bold",
    )

    # ---- Background stage shading (ground truth) ----
    def shade_stages(ax):
        prev_stage = gt_stages[0]
        start_eh = engine_hours[0]
        for i in range(1, len(gt_stages)):
            if gt_stages[i] != prev_stage or i == len(gt_stages) - 1:
                ax.axvspan(
                    start_eh, engine_hours[i],
                    alpha=0.12,
                    color=STAGE_COLORS[prev_stage],
                    zorder=0,
                )
                start_eh = engine_hours[i]
                prev_stage = gt_stages[i]

    # ---- Panel 1: Health Index ----
    ax1 = axes[0]
    shade_stages(ax1)
    ax1.plot(engine_hours, health_indices, color="#2c3e50", linewidth=1.5, label="Health Index")
    ax1.set_ylabel("Health Index (%)")
    ax1.set_ylim(-5, 105)
    ax1.axhline(y=50, color="gray", linestyle="--", alpha=0.4, label="50% threshold")
    ax1.legend(loc="upper right")
    ax1.set_title("Health Index Over Engine Hours")
    ax1.grid(True, alpha=0.3)

    # ---- Panel 2: RUL with confidence band ----
    ax2 = axes[1]
    shade_stages(ax2)
    ax2.fill_between(
        engine_hours, rul_lowers, rul_uppers,
        alpha=0.25, color="#3498db", label="80% confidence band",
    )
    ax2.plot(engine_hours, rul_points, color="#2980b9", linewidth=1.5, label="Predicted RUL")
    ax2.plot(engine_hours, gt_rul, color="#e74c3c", linewidth=1.2, linestyle="--", label="Ground-truth RUL")
    ax2.set_ylabel("RUL (hours)")
    ax2.legend(loc="upper right")
    ax2.set_title("Remaining Useful Life with Confidence Interval")
    ax2.grid(True, alpha=0.3)

    # ---- Panel 3: Predicted vs Ground-Truth Stage ----
    ax3 = axes[2]
    shade_stages(ax3)
    gt_nums = [STAGE_NUM[s] for s in gt_stages]
    pred_nums = [STAGE_NUM[s] for s in pred_stages]
    ax3.plot(engine_hours, gt_nums, color="#e74c3c", linewidth=2.0,
             alpha=0.6, label="Ground Truth")
    ax3.scatter(engine_hours, pred_nums, c="#2c3e50", s=2, alpha=0.5,
                label="Predicted", zorder=5)
    ax3.set_yticks(range(len(STAGE_ORDER)))
    ax3.set_yticklabels([s.replace("_", " ").title() for s in STAGE_ORDER], fontsize=9)
    ax3.set_ylabel("Degradation Stage")
    ax3.set_xlabel("Engine Hours")
    ax3.legend(loc="upper left")
    ax3.set_title("Predicted vs Ground-Truth Degradation Stage")
    ax3.grid(True, alpha=0.3, axis="x")

    # ---- Stage legend ----
    legend_patches = [
        mpatches.Patch(color=STAGE_COLORS[s], alpha=0.3,
                       label=s.replace("_", " ").title())
        for s in STAGE_ORDER
    ]
    fig.legend(
        handles=legend_patches, loc="lower center",
        ncol=5, fontsize=9, frameon=True, title="Ground-Truth Stage (background)",
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    out_path = Path("tests/phm_acceptance_plot.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved: {out_path}")
    plt.close(fig)

    # ---- Print summary stats ----
    print("\n  Summary:")
    print(f"    Health Index:  start={health_indices[0]:.1f}  end={health_indices[-1]:.1f}")
    print(f"    RUL:           start={rul_points[0]:.1f}h   end={rul_points[-1]:.1f}h")
    print(f"    Stage accuracy: {accuracy:.1f}%")
    print(f"    Anomaly score: start={anomaly_scores[0]:.4f}  end={anomaly_scores[-1]:.4f}")

    return accuracy


if __name__ == "__main__":
    acc = main()
    # Exit with error if accuracy is unexpectedly low
    if acc < 80.0:
        print("\nWARNING: Stage accuracy below 80% — investigate!")
        sys.exit(1)
    print("\nPhase 1B acceptance test PASSED.")
