"""Generate PDF from the Phase 1A progress report using matplotlib for simplicity."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
from PIL import Image
import textwrap

docs_dir = Path("docs")
plot_file = docs_dir / "acceptance_plot.png"
pdf_file = docs_dir / "Phase1A_Progress_Report.pdf"

# --- Content pages ---
pages = [
    # Page 1: Title + Summary
    {
        "title": "UAV Engine Digital Twin\nPhase 1A Progress Report",
        "subtitle": "Date: 3 Sep 2026  |  Project: SIH — UAV Engine PHM",
        "body": """
WHAT WE BUILT TODAY
━━━━━━━━━━━━━━━━━━━━

Phase 1A is COMPLETE — the foundational pipeline that detects engine
degradation by comparing real sensor readings against healthy predictions.

THE PIPELINE (3 modules):

  Sensor Data  →  Digital Twin  →  Residual Engine  →  Health Signal
  (12 sensors)    (ML model that     (compares actual
                   predicts healthy    vs expected,
                   values)             outputs z-scores)

MODULES BUILT:

  1. simulation/telemetry_generator.py
     Simulates realistic UAV engine flights with 12 sensors.
     Generates both healthy runs and degrading engine runs.

  2. ml/digital_twin.py
     XGBoost model trained ONLY on healthy engine data.
     Given operating conditions (RPM, throttle, altitude...),
     predicts what a healthy engine's sensors should read.

  3. backend/residual.py
     Calculates difference between actual and healthy predictions.
     Normalizes as z-score so all sensors are comparable.

KEY RESULT:

  z-score near 0  →  Engine healthy (actual matches expected)
  z-score > 3     →  Something is wrong
  z-score > 10    →  CRITICAL degradation

  System shows 15-16x difference between healthy and critical.
"""
    },
    # Page 2: Data & Training
    {
        "title": "Generated Data & Model Training",
        "subtitle": "",
        "body": """
GENERATED DATA (8 files in data/ folder)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Training data (healthy engines):
    healthy_run_01.jsonl  ...  healthy_run_05.jsonl
    → 5,500 samples total (5 flights × 1,100 seconds each)

  Test data (degrading engines):
    trajectory_run_01.jsonl  ...  trajectory_run_03.jsonl
    → 3,300 samples (3 flights, healthy → critical)

  Each sample has 12 sensors:
    INPUTS:  rpm, throttle, map, altitude, ambient_temp
    OUTPUTS: egt, cht, oil_pressure, oil_temp, vibration, fuel_flow


MODEL TRAINING RESULTS
━━━━━━━━━━━━━━━━━━━━━━

  6 XGBoost regressors trained (one per output sensor):

    Sensor          Mean Absolute Error   Quality
    ──────────────  ───────────────────   ───────
    EGT              1.77 °C              Excellent
    CHT              1.20 °C              Excellent
    Oil Pressure     0.60 psi             Excellent
    Oil Temp         0.87 °C              Excellent
    Vibration        0.017 g              Excellent
    Fuel Flow        0.18 L/h             Excellent


ACCEPTANCE TEST (healthy vs critical z-scores)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Sensor          |z| Healthy   |z| Critical   Ratio
    ──────────────  ──────────    ────────────   ─────
    EGT               1.30          20.13        15.5x
    Oil Pressure       1.17          19.02        16.2x
    Vibration          1.25          18.12        14.5x

  21/21 unit tests PASSING.
"""
    },
    # Page 4: How to run
    {
        "title": "How to Run the Demo",
        "subtitle": "Share these commands with the team",
        "body": """
PREREQUISITES
━━━━━━━━━━━━━

  - Python 3.10+ installed
  - Open terminal in: e:\\Project\\SIH\\UAV


STEP 1: Interactive Demo (shows everything step by step)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  .venv\\Scripts\\python.exe demo.py

  Press Enter to advance through 5 steps.
  Shows real data, predictions, residuals, and the plot.


STEP 2: Run All Tests (21/21 should pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  .venv\\Scripts\\python.exe -m pytest tests/ -v


STEP 3: View the Acceptance Plot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Open: tests\\acceptance_plot.png


OTHER COMMANDS:
━━━━━━━━━━━━━━

  # Regenerate synthetic data:
  .venv\\Scripts\\python.exe -m simulation.telemetry_generator

  # Retrain the model:
  .venv\\Scripts\\python.exe -m ml.digital_twin

  # Regenerate the acceptance plot:
  .venv\\Scripts\\python.exe tests/test_acceptance.py


WHAT'S NEXT — PHASE 1B
━━━━━━━━━━━━━━━━━━━━━━

  Phase 1A gives us residuals (the signal).
  Phase 1B uses residuals to build:

    1. Anomaly Detector  →  flags when something is wrong
    2. Fault Classifier  →  identifies WHAT is wrong
    3. Health Index       →  overall engine health (0-100%)
    4. RUL Estimator      →  remaining hours until failure

  Then: Dashboard (Phase 2) and Mission Risk (Phase 3).
"""
    },
]

# --- Generate PDF ---
with PdfPages(str(pdf_file)) as pdf:
    for page in pages:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Title
        ax.text(0.5, 0.95, page["title"],
                transform=ax.transAxes, fontsize=18, fontweight="bold",
                ha="center", va="top", color="#1a5276",
                fontfamily="monospace")

        if page["subtitle"]:
            ax.text(0.5, 0.89, page["subtitle"],
                    transform=ax.transAxes, fontsize=10,
                    ha="center", va="top", color="#7f8c8d",
                    fontfamily="monospace")

        # Body
        ax.text(0.05, 0.85, page["body"].strip(),
                transform=ax.transAxes, fontsize=8.5,
                ha="left", va="top", color="#2c3e50",
                fontfamily="monospace", linespacing=1.3)

        # Footer
        ax.text(0.5, 0.01, "UAV Engine Digital Twin — SIH 2026 — Phase 1A",
                transform=ax.transAxes, fontsize=7, ha="center", color="#bdc3c7")

        pdf.savefig(fig)
        plt.close(fig)

    # Page 3: The acceptance plot
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.97, "Acceptance Test — Visual Proof",
            transform=ax.transAxes, fontsize=18, fontweight="bold",
            ha="center", va="top", color="#1a5276",
            fontfamily="monospace")

    ax.text(0.5, 0.93,
            "Left: Actual (red) vs Expected (blue)  |  Right: Z-score residuals\n"
            "Background: green=healthy, yellow=early, orange=incipient, red=progressive, purple=critical",
            transform=ax.transAxes, fontsize=8, ha="center", va="top",
            color="#7f8c8d", fontfamily="monospace")

    if plot_file.exists():
        img = Image.open(plot_file)
        # Place image in center of page
        ax_img = fig.add_axes([0.03, 0.10, 0.94, 0.80])
        ax_img.imshow(img)
        ax_img.axis("off")

    ax.text(0.5, 0.01, "UAV Engine Digital Twin — SIH 2026 — Phase 1A",
            transform=ax.transAxes, fontsize=7, ha="center", color="#bdc3c7")

    pdf.savefig(fig)
    plt.close(fig)

print(f"PDF saved to: {pdf_file.resolve()}")
