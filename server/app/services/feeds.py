"""Simulated operational feeds: disruption scenarios and a background telemetry / status ticker."""
from __future__ import annotations

import asyncio
import logging
import random

from app.config import settings
from app.core.events import bus
from app.core.utils import add_min, iso, now
from app.data import reference as ref
from app.data.store import store

log = logging.getLogger("arro.feeds")

SCENARIOS = [
    {
        "id": "wx-maa-thunderstorm", "kind": "WEATHER_AIRPORT", "category": "WEATHER",
        "title": "Severe thunderstorm over Chennai airport", "location": "MAA", "asset_id": "MAA-RWY-0725",
        "source": "Weather feed (Open-Meteo observation + nowcast)",
        "description": "Northeast-monsoon convective cell with gusts above 80 km/h and lightning inside 5 km. Runway 07/25 closed and ramp operations suspended.",
    },
    {
        "id": "cyclone-maa", "kind": "WEATHER_AIRPORT", "category": "WEATHER",
        "title": "Cyclonic storm closes Chennai airport", "location": "MAA", "asset_id": "MAA-RWY-1230",
        "source": "IMD cyclone bulletin + Open-Meteo nowcast",
        "description": "Cyclonic storm crossing the coast near Chennai: sustained winds above 70 km/h, torrential rain and water-logging on Runway 12/30. All movements suspended.",
        "readings": {"wind_gust_kmh": 108, "wind_kmh": 74, "visibility_m": 450, "lightning_km": 6.0, "precip_mm_h": 52},
        "forecast_min": 240, "condition": "Cyclonic storm",
    },
    {
        "id": "aog-maa-hydraulic", "kind": "AIRCRAFT_FAULT", "category": "ASSET_HEALTH",
        "title": "Hydraulic fault grounds an aircraft at Chennai", "location": "MAA", "asset_id": None,
        "source": "Asset-health stream (aircraft condition monitoring)",
        "description": "Hydraulic system B pressure loss reported before departure from Chennai. Aircraft not dispatchable under the MEL.",
    },
]


def scenario_list() -> list[dict]:
    hidden = {"readings", "forecast_min", "condition"}
    return [{k: v for k, v in s.items() if k not in hidden} for s in SCENARIOS]


def _pick_grounded_aircraft(node: str) -> tuple[str, dict] | None:
    ref_time = now()
    best = None
    for vid, legs in store.rotations.items():
        for i, tid in enumerate(legs):
            t = store.trips[tid]
            if t["origin"] != node or t["cancelled"]:
                continue
            dep = store.est_dep(t)
            if add_min(ref_time, 15) <= dep <= add_min(ref_time, 240) and len(legs) - i >= 2:
                if best is None or dep < best[2]:
                    best = (vid, t, dep)
    if best is None:
        for vid, legs in store.rotations.items():
            for tid in legs:
                t = store.trips[tid]
                if t["origin"] == node and store.est_dep(t) > add_min(ref_time, 10) and not t["cancelled"]:
                    if best is None or store.est_dep(t) < best[2]:
                        best = (vid, t, store.est_dep(t))
    return (best[0], best[1]) if best else None


def build_event(scenario_id: str) -> dict:
    spec = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if spec is None:
        raise KeyError(scenario_id)
    received = now()
    event = {
        "id": store.next_id("EVT", 5001),
        "scenario_id": spec["id"], "kind": spec["kind"], "category": spec["category"],
        "title": spec["title"], "source": spec["source"], "description": spec["description"],
        "received_at": iso(received), "location": spec["location"], "asset_id": spec["asset_id"],
        "corroborated": spec["category"] == "WEATHER",
    }
    with store.lock:
        if spec["kind"] == "WEATHER_AIRPORT":
            live = store.weather.get(spec["location"], {})
            event["baseline"] = {"wind_gust_kmh": live.get("gust_kmh"), "visibility_m": live.get("visibility_m"),
                                 "precip_mm_h": live.get("precip_mm"), "temperature_c": live.get("temperature_c"),
                                 "observed_by": live.get("source", "Simulated")}
            r = {"wind_gust_kmh": 86, "wind_kmh": 52, "visibility_m": 700, "lightning_km": 3.4, "precip_mm_h": 31,
                 **spec.get("readings", {})}
            r["temperature_c"] = round((live.get("temperature_c") or 29) - 7, 1)
            event["readings"] = r
            event["forecast"] = {"duration_min": spec.get("forecast_min", 150), "source": "Nowcast cell tracking"}
            store.weather[spec["location"]] = {
                **live, "gust_kmh": r["wind_gust_kmh"], "wind_kmh": r["wind_kmh"], "visibility_m": r["visibility_m"],
                "precip_mm": r["precip_mm_h"], "condition": spec.get("condition", "Severe thunderstorm"),
                "weather_code": 99, "severe": True,
                "source": f"{live.get('source', 'Simulated')} + nowcast", "observed_at": iso(received),
            }
            asset_update = {"standing_water_mm": round(r["precip_mm_h"] / 5, 1), "crosswind_kt": round(r["wind_gust_kmh"] / 2.8, 1),
                            "friction_coefficient": 0.38}
        else:
            picked = _pick_grounded_aircraft(spec["location"])
            if not picked:
                raise ValueError("No aircraft currently on the ground at the scenario airport")
            vid, next_trip = picked
            event["asset_id"] = vid
            event["title"] = f"Hydraulic fault grounds {vid} at {ref.display_code(spec['location'])}"
            event["readings"] = {"hyd_sys_b_psi": 1450, "hyd_qty_pct": 41, "ecam": "HYD B LO PR"}
            event["next_departure"] = next_trip["number"]
            asset_update = {"hyd_sys_b_psi": 1450.0}
        asset = store.assets[event["asset_id"]]
        asset["metrics"].update(asset_update)
        asset["status"] = "OUT_OF_SERVICE"
        asset["health"] = 18 if spec["category"] == "ASSET_HEALTH" else 34
        event["asset_criticality"] = asset["criticality"]
        event["asset_name"] = asset["name"]
    return event


def publish_feed(source: str, level: str, title: str, detail: str = "", ref_id: str | None = None) -> dict:
    item = {"id": store.next_id("FD", 1), "ts": iso(now()), "source": source, "level": level,
            "title": title, "detail": detail, "ref": ref_id}
    store.add_feed(item)
    bus.publish("feed", item)
    return item


def _telemetry_tick(rng: random.Random) -> None:
    with store.lock:
        candidates = [a for a in store.assets.values() if a["status"] == "OPERATIONAL"]
        asset = rng.choice(candidates)
        for k, base in asset["baseline"].items():
            if isinstance(base, (int, float)) and base:
                asset["metrics"][k] = round(base * rng.uniform(0.985, 1.015), 2)
        asset["health"] = max(80, min(99, asset["health"] + rng.choice([-1, 0, 0, 1])))
        name, health = asset["name"], asset["health"]
    publish_feed("ASSET", "info", f"{name} telemetry nominal", f"Health index {health}%", asset["id"])


def _ops_tick(rng: random.Random) -> None:
    ref_time = now()
    with store.lock:
        soon = [t for t in store.trips.values()
                if not t["cancelled"] and 0 <= (store.est_dep(t) - ref_time).total_seconds() <= 3600]
        if not soon:
            return
        t = rng.choice(soon)
        status = store.trip_status(t)
        label = {"BOARDING": "boarding", "DELAYED": f"delayed {t['delay_min']} min", "ON_TIME": "on schedule"}.get(status, status.lower())
        title = f"{t['number']} {ref.display_code(t['origin'])}-{ref.display_code(t['destination'])} {label}"
        detail = f"Gate {t['gate']} | departs {store.est_dep(t).strftime('%H:%M')}"
        level = "warning" if status == "DELAYED" else "info"
    publish_feed("OPS", level, title, detail, t["id"])


def _weather_tick(rng: random.Random) -> None:
    with store.lock:
        if not store.weather:
            return
        w = rng.choice(list(store.weather.values()))
    level = "critical" if w.get("severe") else "info"
    publish_feed("WEATHER", level, f"{w['code']} {w.get('condition', '')}",
                 f"{w.get('temperature_c')} C, wind {w.get('wind_kmh')} km/h, gusts {w.get('gust_kmh')} km/h ({w.get('source')})", w["code"])


async def telemetry_loop() -> None:
    rng = random.Random()
    ticks = [_telemetry_tick, _ops_tick, _ops_tick, _weather_tick]
    i = 0
    while True:
        try:
            ticks[i % len(ticks)](rng)
        except Exception as exc:  # noqa: BLE001
            log.debug("telemetry tick failed: %s", exc)
        i += 1
        await asyncio.sleep(settings.telemetry_interval_s)
