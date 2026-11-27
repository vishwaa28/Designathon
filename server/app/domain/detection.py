"""Threshold-based disruption detection for weather and asset-health events."""
from __future__ import annotations

from app.core.utils import add_min, iso, parse_dt
from app.data import reference as ref

SEVERITY_ORDER = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def _trigger(signal: str, value, threshold, unit: str, rule: str, breached: bool) -> dict:
    return {"signal": signal, "value": value, "threshold": threshold, "unit": unit, "rule": rule, "breached": breached}


def assess(event: dict) -> dict:
    r = event["readings"]
    received = parse_dt(event["received_at"])
    kind = event["kind"]
    triggers: list[dict] = []
    scope: dict

    if kind == "WEATHER_AIRPORT":
        triggers = [
            _trigger("Wind gusts", r["wind_gust_kmh"], 65, "km/h", "Crosswind / gust limit for ground handling and take-off", r["wind_gust_kmh"] >= 65),
            _trigger("Visibility", r["visibility_m"], 1000, "m", "Below CAT-I minima without low-visibility procedures", r["visibility_m"] < 1000),
            _trigger("Lightning distance", r["lightning_km"], 8, "km", "Ramp operations suspended inside 8 km lightning radius", r["lightning_km"] < 8),
            _trigger("Precipitation rate", r["precip_mm_h"], 25, "mm/h", "Runway contamination risk above 25 mm/h", r["precip_mm_h"] >= 25),
        ]
        duration = event["forecast"]["duration_min"]
        scope = {"type": "AIRPORT_CLOSURE", "node": event["location"],
                 "start": iso(add_min(received, 10)), "end": iso(add_min(received, 10 + duration))}
        dtype = "Airport closure (weather)"
    elif kind == "AIRCRAFT_FAULT":
        triggers = [
            _trigger("Hydraulic system B pressure", r["hyd_sys_b_psi"], 2800, "psi", "MEL: dispatch not permitted below 2800 psi", r["hyd_sys_b_psi"] < 2800),
            _trigger("Fluid quantity", r["hyd_qty_pct"], 60, "%", "Reservoir below 60 % indicates leak", r["hyd_qty_pct"] < 60),
            _trigger("ECAM caution", r["ecam"], "none", "", "Active caution blocks dispatch", True),
        ]
        scope = {"type": "VEHICLE_GROUNDED", "vehicle_id": event["asset_id"], "node": event["location"],
                 "start": iso(received), "end": iso(add_min(received, 240))}
        dtype = "Aircraft on ground (technical)"
    else:
        return {"is_disruption": False, "severity": "LOW", "triggers": [], "type": "Unknown", "confidence": 0.3}

    breached = sum(1 for t in triggers if t["breached"])
    critical_asset = event.get("asset_criticality") == "CRITICAL"
    level = min(3, breached - 1 + (1 if critical_asset else 0))
    severity = SEVERITY_ORDER[max(0, level)]
    confidence = round(min(0.97, 0.62 + 0.09 * breached + (0.05 if event.get("corroborated") else 0)), 2)
    location_label = ref.display_code(event["location"])
    return {
        "is_disruption": breached >= 1,
        "type": dtype,
        "severity": severity,
        "triggers": triggers,
        "breached": breached,
        "scope": scope,
        "location_label": location_label,
        "confidence": confidence,
        "initial_window": {"start": scope["start"], "end": scope["end"]},
    }
