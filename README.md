# UAV Engine Digital Twin — Prognostic Health Management

A real-time UAV piston engine health monitoring system that uses a **Digital Twin** + **Machine Learning** pipeline to detect anomalies, classify faults, estimate remaining useful life (RUL), and compute an overall health index.

## Features

- **Digital Twin** — XGBoost models predict what a *healthy* engine should look like under current operating conditions
- **Residual Engine** — Compares actual vs. expected sensor values to detect degradation
- **Anomaly Detection** — Flags abnormal sensor patterns using Isolation Forest
- **Fault Classification** — Identifies degradation stage (healthy → critical)
- **RUL Estimation** — Predicts remaining useful life with confidence intervals
- **Health Index** — Single 0–100% score for engine health
- **Live Dashboard** — Real-time web UI with WebSocket streaming, 3D engine visualization, and sensor charts

## Quick Start

### Prerequisites

- **Python 3.10+** (download from [python.org](https://www.python.org/downloads/))
- **Git** (download from [git-scm.com](https://git-scm.com/downloads))
- **VS Code** (recommended editor — [download here](https://code.visualstudio.com/))
- **Windows OS**

### Setup (Step by Step)

**Step 1:** Clone the repo and open it in VS Code

```
git clone <your-repo-url>
cd UAV
code .
```

**Step 2:** Open the **integrated terminal** inside VS Code

> Press **Ctrl + `** (backtick key, below Esc) to open the terminal panel at the bottom of VS Code. All the commands below should be typed here.

**Step 3:** Create a Python virtual environment

```
python -m venv .venv
```

**Step 4:** Activate the virtual environment

```
.venv\Scripts\activate
```

> After running this, you should see `(.venv)` appear at the beginning of your terminal prompt. This means the virtual environment is active.

**Step 5:** Install all dependencies

```
pip install -r requirements.txt
```

> This will take a minute — it installs NumPy, Pandas, XGBoost, FastAPI, etc.

### Run the Demo

Once setup is done, you can launch the demo in two ways:

**Option A:** Double-click `start_demo.bat` in the file explorer

**Option B:** Run from the VS Code terminal:

```
.\start_demo.bat
```

This will:
1. Start the backend API server (FastAPI + Uvicorn)
2. Open the live dashboard in your browser at `http://127.0.0.1:8000/`
3. Start streaming simulated drone telemetry data

> ⚠️ **Important:** You must complete the **Setup** steps (especially creating `.venv` and installing dependencies) before running the demo. Without this, the demo will fail.

## Project Structure

```
UAV/
├── start_demo.bat           # One-click demo launcher
├── demo_stream.py           # Streams telemetry data to the API
├── demo.py                  # Interactive CLI demo walkthrough
├── requirements.txt         # Python dependencies
│
├── frontend/                # Web dashboard (HTML/CSS/JS)
│   ├── index.html           # Dashboard page
│   ├── style.css            # Styles
│   ├── app.js               # Dashboard logic + WebSocket client
│   └── assets/              # SVG engine assets
│
├── backend/                 # FastAPI backend
│   ├── api.py               # REST + WebSocket API
│   └── residual.py          # Residual calculation engine
│
├── ml/                      # Machine learning models
│   ├── digital_twin.py      # Digital Twin (XGBoost regressors)
│   ├── anomaly_detector.py  # Isolation Forest anomaly detection
│   ├── fault_classifier.py  # Degradation stage classifier
│   ├── rul_estimator.py     # Remaining Useful Life estimator
│   ├── health_index.py      # Health index calculation
│   ├── phm_core.py          # Unified PHM pipeline
│   └── artifacts/           # Pre-trained model files (.joblib)
│
├── simulation/              # Synthetic telemetry generator
│   └── telemetry_generator.py
│
├── data/                    # Synthetic flight data (JSONL/CSV)
│
├── tests/                   # Unit & acceptance tests
│
├── 3D/                      # SVG sensor/engine assets
│
└── docs/                    # Reports & documentation
```

## Other Commands

> 💡 Run these in the **VS Code terminal** (`Ctrl + ``) with the virtual environment activated.

```
# Run all tests (should show all passing):
.venv\Scripts\python.exe -m pytest tests/ -v

# Run the interactive CLI demo:
.venv\Scripts\python.exe demo.py

# Regenerate synthetic data:
.venv\Scripts\python.exe -m simulation.telemetry_generator

# Retrain the Digital Twin model:
.venv\Scripts\python.exe -m ml.digital_twin
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| ML Models | XGBoost, Scikit-learn |
| Backend   | FastAPI, Uvicorn, WebSockets |
| Frontend  | Vanilla HTML/CSS/JS |
| Data      | NumPy, Pandas |
