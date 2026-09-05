import json
import time
import requests
import argparse
from pathlib import Path

API_URL = "http://localhost:8000/api/telemetry"
DATA_FILE = Path("data/trajectory_run_01.jsonl")

def stream_flight(speed_factor=10):
    if not DATA_FILE.exists():
        print(f"Error: Could not find {DATA_FILE}")
        return

    print("========================================")
    print(f"[START] Starting Flight Simulation Stream (Speed: {speed_factor}x)")
    print(f"[API] Broadcasting to: {API_URL}")
    print("========================================\n")

    with open(DATA_FILE, 'r') as f:
        lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i]
            try:
                sample = json.loads(line.strip())
                
                # Send the sample to the backend API
                response = requests.post(API_URL, json=sample)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"[{sample['engine_hours']:.1f}h] Transmitted. Health: {data.get('health_index', 'N/A')}%")
                else:
                    print(f"Error {response.status_code}: {response.text}")
                
                # Check for dynamic speed changes
                try:
                    speed_resp = requests.get(API_URL.replace("/telemetry", "/speed"), timeout=0.5)
                    if speed_resp.status_code == 200:
                        speed_factor = speed_resp.json().get("speed", 10)
                except requests.RequestException:
                    pass
                
                i += speed_factor
                time.sleep(1)
                
            except json.JSONDecodeError:
                i += 1
                continue
            except requests.ConnectionError:
                print("Error: Could not connect to the API. Is the server running?")
                print("Start it with: uvicorn backend.api:app --reload")
                break
            except KeyboardInterrupt:
                print("\n[STOP] Flight Simulation Stopped.")
                break

if __name__ == "__main__":
    stream_flight()
