import os
import json
import uuid
import datetime
from pathlib import Path
import re

DATA_DIR = Path(__file__).parent.parent / "data" / "events"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SVG_PATH = Path(__file__).parent.parent / "frontend" / "assets" / "engine.svg"

class EventManager:
    def __init__(self):
        self.current_event_id = None
        self.active_red_sensors = set()
        
        # Determine next EVT ID
        self.next_id_num = 1
        for d in DATA_DIR.iterdir():
            if d.is_dir() and d.name.startswith("EVT_"):
                try:
                    num = int(d.name.split("_")[1])
                    if num >= self.next_id_num:
                        self.next_id_num = num + 1
                except ValueError:
                    pass

    def _generate_event_id(self):
        eid = f"EVT_{self.next_id_num:04d}"
        self.next_id_num += 1
        return eid

    def process_telemetry(self, raw_data, residual_z, phm_result):
        threshold = 3.0
        
        # Determine which sensors are RED
        current_red_sensors = set()
        sensor_names = {
            'egt': 'EGT Sensor',
            'cht': 'CHT Sensor',
            'vibration': 'Vibration Sensor',
            'oil_pressure': 'Oil Sensor',
            'fuel_flow': 'Fuel Sensor'
        }
        
        affected_components = []
        for sensor, z in residual_z.items():
            if sensor in sensor_names and abs(z) > threshold:
                current_red_sensors.add(sensor)
                affected_components.append({
                    "sensor_id": sensor,
                    "sensor_name": sensor_names[sensor],
                    "z_score": float(z)
                })
        
        is_new_anomaly = len(current_red_sensors) > 0 and len(self.active_red_sensors) == 0
        is_anomaly_cleared = len(current_red_sensors) == 0 and len(self.active_red_sensors) > 0
        
        if is_new_anomaly:
            # Create NEW event
            self.current_event_id = self._generate_event_id()
            self._create_event(self.current_event_id, raw_data, residual_z, phm_result, affected_components)
        elif is_anomaly_cleared and self.current_event_id:
            # Close event
            self._close_event(self.current_event_id)
            self.current_event_id = None
            
        self.active_red_sensors = current_red_sensors

    def _close_event(self, event_id):
        json_path = DATA_DIR / event_id / "event.json"
        if json_path.exists():
            try:
                with open(json_path, "r") as f:
                    data = json.load(f)
                data["event_status"] = "closed"
                with open(json_path, "w") as f:
                    json.dump(data, f, indent=4)
            except:
                pass

    def _create_event(self, event_id, raw_data, residual_z, phm_result, affected_components):
        event_dir = DATA_DIR / event_id
        event_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.datetime.fromtimestamp(raw_data['timestamp']).isoformat()
        
        # Primary component
        primary = affected_components[0] if affected_components else {}
        
        event_json = {
            "event_id": event_id,
            "timestamp": timestamp_str,
            "recorded_at": datetime.datetime.now().isoformat(),
            "affected_components": affected_components,
            "affected_component": {
                "sensor_id": primary.get("sensor_id"),
                "sensor_name": primary.get("sensor_name"),
                "parameter": primary.get("sensor_id"),
                "component": primary.get("sensor_name")
            },
            "anomaly": {
                "detected": phm_result.get("anomaly", True),
                "score": float(phm_result.get("anomaly_score", 0)),
                "z_score": primary.get("z_score", 0)
            },
            "health": {
                "health_index": float(phm_result.get("health_index", 100)),
                "rul": float(phm_result.get("rul_hours", 0)),
                "degradation_stage": str(phm_result.get("degradation_stage", "healthy"))
            },
            "sensor_data": {
                "rpm": raw_data.get("rpm"),
                "throttle": raw_data.get("throttle"),
                "map": raw_data.get("map"),
                "altitude": raw_data.get("altitude"),
                "ambient_temp": raw_data.get("ambient_temp"),
                "egt": raw_data.get("egt"),
                "cht": raw_data.get("cht"),
                "oil_pressure": raw_data.get("oil_pressure"),
                "oil_temp": raw_data.get("oil_temp"),
                "vibration": raw_data.get("vibration"),
                "fuel_flow": raw_data.get("fuel_flow"),
                "engine_hours": raw_data.get("engine_hours")
            },
            "image": {
                "snapshot": "snapshot.svg"
            },
            "event_status": "open"
        }
        
        with open(event_dir / "event.json", "w") as f:
            json.dump(event_json, f, indent=4)
            
        self._generate_snapshot(event_dir / "snapshot.svg", event_json)

    def _generate_snapshot(self, out_path, event_json):
        # Read engine.svg
        if not SVG_PATH.exists():
            return
            
        with open(SVG_PATH, "r", encoding="utf-8") as f:
            svg = f.read()
            
        # Highlight RED components
        for comp in event_json["affected_components"]:
            sensor_id = comp["sensor_id"]
            if sensor_id == "egt":
                svg = svg.replace('<g id="egt-sensor">', '<g id="egt-sensor" stroke="#ff0000" stroke-width="3" filter="drop-shadow(0 0 12px rgba(255,0,0,1))">')
            elif sensor_id == "cht":
                svg = svg.replace('<g id="cht-sensor">', '<g id="cht-sensor" stroke="#ff0000" stroke-width="3" filter="drop-shadow(0 0 12px rgba(255,0,0,1))">')
            elif sensor_id == "vibration":
                svg = svg.replace('<g id="vibration-sensor">', '<g id="vibration-sensor" stroke="#ff0000" stroke-width="3" filter="drop-shadow(0 0 12px rgba(255,0,0,1))">')
            elif sensor_id == "oil_pressure":
                svg = svg.replace('<g id="oil-sensor">', '<g id="oil-sensor" stroke="#ff0000" stroke-width="3" filter="drop-shadow(0 0 12px rgba(255,0,0,1))">')
            elif sensor_id == "fuel_flow":
                svg = svg.replace('<g id="fuel-sensor">', '<g id="fuel-sensor" stroke="#ff0000" stroke-width="3" filter="drop-shadow(0 0 12px rgba(255,0,0,1))">')
                
        sd = event_json["sensor_data"]
        recorded_str = datetime.datetime.fromisoformat(event_json["recorded_at"]).strftime("%Y-%m-%d %H:%M:%S")
        labels_html = f'''
        <g id="event-annotations" font-family="monospace" font-size="24" fill="#ffffff">
            <!-- Background for annotations -->
            <rect x="30" y="30" width="450" height="280" fill="rgba(0,0,0,0.8)" stroke="#ff0000" stroke-width="2" rx="10"/>
            <text x="50" y="70" fill="#ff0000" font-weight="bold" font-size="28">{event_json["event_id"]} ANOMALY</text>
            <text x="50" y="110">Time: {recorded_str}</text>
            <text x="50" y="150">Stage: {event_json["health"]["degradation_stage"].upper()}</text>
            <text x="50" y="190">Health Index: {event_json["health"]["health_index"]:.1f}%</text>
            <text x="50" y="230">RUL: {event_json["health"]["rul"]:.1f} hrs</text>
            
            <g font-size="20">
                <!-- S01 RPM -> Propeller -->
                <text x="1800" y="600" fill="#000000">S01 RPM: {sd.get("rpm",0):.0f}</text>
                <line x1="1790" y1="610" x2="1600" y2="650" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S02 THR -> Top Intake -->
                <text x="1200" y="100" fill="#000000">S02 THR: {sd.get("throttle",0):.1f}%</text>
                <line x1="1250" y1="110" x2="1350" y2="250" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S03 MAP -> Intake Pipes -->
                <text x="1100" y="80">S03 MAP: {sd.get("map",0):.1f}</text>
                <line x1="1150" y1="90" x2="1200" y2="250" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S04 ALT -> Intake/Env -->
                <text x="2000" y="200">S04 ALT: {sd.get("altitude",0):.0f}m</text>
                <line x1="1990" y1="210" x2="1700" y2="400" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S05 AMB -> Front Env -->
                <text x="2000" y="300">S05 AMB: {sd.get("ambient_temp",0):.1f}C</text>
                <line x1="1990" y1="310" x2="1750" y2="450" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S06 EGT -> Bottom Exhaust -->
                <text x="1400" y="850" fill="#000000">S06 EGT: {sd.get("egt",0):.1f}C</text>
                <line x1="1390" y1="840" x2="1280" y2="760" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S07 CHT -> Top Cylinders -->
                <text x="1500" y="400" fill="#000000">S07 CHT: {sd.get("cht",0):.1f}C</text>
                <line x1="1490" y1="410" x2="1350" y2="480" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S08 OILP -> Oil Sump -->
                <text x="750" y="1000" fill="#000000">S08 OILP: {sd.get("oil_pressure",0):.1f}</text>
                <line x1="800" y1="990" x2="1000" y2="750" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S09 OILT -> Oil Sump -->
                <text x="1050" y="1050" fill="#000000">S09 OILT: {sd.get("oil_temp",0):.1f}C</text>
                <line x1="1100" y1="1040" x2="1050" y2="750" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S10 VIB -> Engine Block -->
                <text x="1050" y="200">S10 VIB: {sd.get("vibration",0):.2f}</text>
                <line x1="1100" y1="210" x2="1140" y2="400" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S11 FUEL -> Fuel Lines -->
                <text x="700" y="200">S11 FUEL: {sd.get("fuel_flow",0):.1f}</text>
                <line x1="750" y1="210" x2="850" y2="350" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
                
                <!-- S12 ENG HOURS -> Engine Case -->
                <text x="600" y="550" fill="#000000">S12 ENG HOURS: {sd.get("engine_hours",0):.1f}h</text>
                <line x1="650" y1="560" x2="800" y2="600" stroke="#ffaa00" stroke-width="2" marker-end="url(#arrowhead)"/>
            </g>
            
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#ffaa00" />
                </marker>
            </defs>
        </g>
        '''
        
        svg = svg.replace("</svg>", labels_html + "\n</svg>")
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)

    def get_events(self):
        events = []
        for d in sorted(DATA_DIR.iterdir(), reverse=True):
            if d.is_dir() and d.name.startswith("EVT_"):
                json_path = d / "event.json"
                if json_path.exists():
                    try:
                        with open(json_path, "r") as f:
                            data = json.load(f)
                            events.append(data)
                    except:
                        pass
        return events

    def get_event(self, event_id):
        json_path = DATA_DIR / event_id / "event.json"
        if json_path.exists():
            try:
                with open(json_path, "r") as f:
                    return json.load(f)
            except:
                pass
        return None

event_manager = EventManager()
