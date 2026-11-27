"""Infrastructure fault triage: probable-cause ranking, crew dispatch and repair-window estimation."""
from __future__ import annotations

from app.core.utils import add_min, iso, now, parse_dt
from app.data import reference as ref
from app.data.store import store

FAULT_MODELS = {
    "SIGNAL": {
        "skill": "SIGNALLING", "diagnosis_min": 20,
        "causes": [
            {"cause": "Relay contact degradation in route-relay interlocking", "probability": 0.46, "repair": (60, 110), "part": "Q-series plug-in relay", "local": True},
            {"cause": "Insulated rail joint failure dropping the track circuit", "probability": 0.31, "repair": (90, 170), "part": "Glued insulated rail joint kit", "local": True},
            {"cause": "Power fluctuation in relay-room integrated power supply", "probability": 0.23, "repair": (40, 80), "part": "IPS rectifier module", "local": False},
        ],
        "safety": ["Block section protected; trains on Paper Line Clear authority only",
                   "Disconnection memo with station master before touching interlocking",
                   "Lookout person posted on both lines during track work"],
        "checklist": ["Megger test on relay group", "Check IRJ insulation at km 18/4", "Verify IPS output voltage", "Joint testing with station master before reconnection"],
    },
    "TRACK_CIRCUIT": {
        "skill": "TRACK", "diagnosis_min": 30,
        "causes": [
            {"cause": "Ballast washout and water ingress at culvert", "probability": 0.55, "repair": (150, 300), "part": "Ballast rake and boulder packing", "local": True},
            {"cause": "Track circuit shunt failure from submerged rails", "probability": 0.30, "repair": (60, 120), "part": "Track circuit feed set", "local": True},
            {"cause": "Embankment slip near cutting", "probability": 0.15, "repair": (240, 420), "part": "Sand bags and gabions", "local": False},
        ],
        "safety": ["No movement until water recedes below rail level", "Patrolman verification of formation", "Speed restriction 20 km/h after restoration"],
        "checklist": ["Water level monitoring every 15 min", "Ballast profile check", "Track circuit reset and testing", "Joint inspection with permanent-way inspector"],
    },
    "RUNWAY": {
        "skill": "AIRSIDE", "diagnosis_min": 10,
        "causes": [
            {"cause": "Storm debris (FOD) on runway and taxiways", "probability": 0.50, "repair": (20, 40), "part": "FOD sweeper", "local": True},
            {"cause": "Standing water above 3 mm limiting braking action", "probability": 0.30, "repair": (30, 60), "part": "Friction tester and drainage crew", "local": True},
            {"cause": "Lightning damage to approach or edge lighting", "probability": 0.20, "repair": (60, 120), "part": "AGL lamp assemblies", "local": True},
        ],
        "safety": ["Runway inspection only after lightning alert is cancelled", "ATC coordination for vehicle movement on runway", "Friction measurement before reopening"],
        "checklist": ["Full-length FOD walk", "Runway friction test (GRF report)", "AGL serviceability check", "Issue NOTAM cancellation"],
    },
    "AIRCRAFT": {
        "skill": "AIRCRAFT", "diagnosis_min": 25,
        "causes": [
            {"cause": "Engine-driven pump failure on hydraulic system B", "probability": 0.52, "repair": (180, 260), "part": "Engine-driven hydraulic pump", "local": False},
            {"cause": "Hydraulic line leak at main landing gear bay", "probability": 0.33, "repair": (120, 220), "part": "Hydraulic line and seals kit", "local": True},
            {"cause": "Faulty pressure transducer", "probability": 0.15, "repair": (45, 90), "part": "Pressure transducer", "local": True},
        ],
        "safety": ["Hydraulic system depressurised and tagged", "Aircraft chocked and gear pins installed", "Duplicate inspection by second B1 engineer"],
        "checklist": ["Leak check under pressure", "Pump case drain flow test", "Replace and bleed system", "Engine ground run and CRS release"],
    },
}
PARTS_LEAD_MIN = 150


def triage(asset: dict, detection: dict, adjustments: dict | None = None) -> dict:
    adjustments = adjustments or {}
    model = FAULT_MODELS.get(asset["type"], FAULT_MODELS["RUNWAY"])
    ref_time = now()
    teams = [t for t in store.teams.values() if t["skill"] == model["skill"]]
    team = min(teams, key=lambda t: (t["status"] != "AVAILABLE", t["eta_min"]))
    on_site = add_min(ref_time, team["eta_min"])

    hazard_clear = ref_time
    if detection["scope"]["type"] == "AIRPORT_CLOSURE":
        hazard_clear = parse_dt(detection["scope"]["end"])
    work_start = max(on_site, hazard_clear)

    causes = sorted(model["causes"], key=lambda c: -c["probability"])
    top = causes[0]
    shift = int(adjustments.get("window_shift_min", 0))
    lead = 0 if top["local"] else PARTS_LEAD_MIN
    p50_min = model["diagnosis_min"] + (top["repair"][0] + top["repair"][1]) / 2 + lead
    p90_min = model["diagnosis_min"] + max(
        c["repair"][1] + (0 if c["local"] else PARTS_LEAD_MIN) for c in causes if c["probability"] >= 0.2)
    p50 = add_min(work_start, p50_min + shift)
    p90 = add_min(work_start, max(p90_min, p50_min) + shift)

    parts = []
    for c in causes:
        parts.append({"part": c["part"], "available": c["local"],
                      "source": f"Local stores ({ref.display_code(team['base'])})" if c["local"] else "Central stores, BLR (150 min lead)"})
    return {
        "asset": store.asset_view(asset),
        "fault_type": detection["type"],
        "probable_causes": [{"cause": c["cause"], "probability": c["probability"],
                             "repair_min": list(c["repair"])} for c in causes],
        "team": {"id": team["id"], "name": team["name"], "members": team["members"],
                 "eta_min": team["eta_min"], "base": ref.display_code(team["base"])},
        "dispatch_at": iso(ref_time),
        "on_site_at": iso(on_site),
        "work_start": iso(work_start),
        "restoration": {"p50": iso(p50), "p90": iso(p90)},
        "parts": parts,
        "safety_notes": model["safety"],
        "checklist": model["checklist"],
        "window_shift_min": shift,
    }
