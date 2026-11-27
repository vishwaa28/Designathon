"""Crowd analytics: turns head counts from camera frames into density, queue wait and reroute plans.

Everything here is deterministic and unit-testable. The vision model only supplies the counts; the
floor area, service rates and thresholds come from ``app.data.reference`` (CAMERAS, DENSITY_BANDS).
"""
from __future__ import annotations

import math
import statistics
from collections import Counter

from app.data import reference as ref

MOVEMENTS = ("flowing", "slow", "stationary")
SMOOTHING_SAMPLES = 5            # observations in the rolling median
SMOOTHING_WINDOW_S = 180         # ignore observations older than this relative to the newest
STALE_AFTER_S = 120              # no new frame for this long -> the tile is marked stale
MAX_PEOPLE = 600
LEVEL_ORDER = {name: i for i, (name, _) in enumerate(ref.DENSITY_BANDS)}


def density_level(density: float) -> str:
    level = ref.DENSITY_BANDS[0][0]
    for name, floor in ref.DENSITY_BANDS:
        if density >= floor:
            level = name
    return level


def throughput(cam: dict) -> float:
    """Passengers processed per minute with the configured number of open service points."""
    return max(0.1, cam["service_points"] * cam["rate_per_point"])


def wait_minutes(queue: int, cam: dict, extra_points: int = 0) -> float:
    rate = max(0.1, (cam["service_points"] + extra_points) * cam["rate_per_point"])
    return round(queue / rate, 1)


def validate(raw: dict | None) -> dict | None:
    """Coerce the model answer into safe integers. Returns None when no usable count is present."""
    if not isinstance(raw, dict):
        return None

    def num(key: str) -> float | None:
        try:
            return float(raw[key])
        except (KeyError, TypeError, ValueError):
            return None

    bands = [num(k) for k in ("foreground", "midground", "background")]
    total = num("people_total")
    if total is None and all(b is not None for b in bands):
        total = sum(bands)  # type: ignore[arg-type]
    if total is None:
        return None
    total = int(max(0, min(MAX_PEOPLE, round(total))))
    queue = num("people_in_queue")
    queue = total if queue is None else int(max(0, min(total, round(queue))))
    lanes = num("queue_lanes")
    conf = num("confidence")
    movement = str(raw.get("movement", "")).lower()
    return {
        "people_total": total,
        "people_in_queue": queue,
        "queue_lanes": int(max(0, min(15, round(lanes)))) if lanes is not None else None,
        "movement": movement if movement in MOVEMENTS else "slow",
        "confidence": round(max(0.0, min(1.0, conf)), 2) if conf is not None and 0 <= conf <= 1 else 0.6,
    }


def observation_metrics(cam: dict, obs: dict) -> dict:
    density = round(obs["people_total"] / cam["area_m2"], 2)
    return {"density": density, "level": density_level(density), "wait_min": wait_minutes(obs["people_in_queue"], cam)}


def smooth(rows: list[dict]) -> dict | None:
    """Rolling median over the most recent observations so one noisy frame cannot swing the picture."""
    if not rows:
        return None
    newest = rows[-1]["_ts"]
    recent = [r for r in rows[-SMOOTHING_SAMPLES:] if newest - r["_ts"] <= SMOOTHING_WINDOW_S] or [rows[-1]]
    lanes = [r["queue_lanes"] for r in recent if r.get("queue_lanes") is not None]
    return {
        "people_total": int(round(statistics.median(r["people_total"] for r in recent))),
        "people_in_queue": int(round(statistics.median(r["people_in_queue"] for r in recent))),
        "queue_lanes": int(round(statistics.median(lanes))) if lanes else None,
        "movement": Counter(r["movement"] for r in recent).most_common(1)[0][0],
        "confidence": round(sum(r["confidence"] or 0 for r in recent) / len(recent), 2),
        "samples": len(recent),
    }


def needs_action(state: dict) -> bool:
    return state["status"] != "no_data" and (
        LEVEL_ORDER.get(state["level"], 0) >= LEVEL_ORDER["HIGH"] or state["wait_min"] >= ref.QUEUE_WAIT_ALERT_MIN)


def rollup(terminal: dict, cams: list[dict]) -> dict:
    live = [c for c in cams if c["status"] != "no_data"]
    people = sum(c["people_total"] for c in live)
    queue = sum(c["people_in_queue"] for c in live)
    area = sum(c["area_m2"] for c in live)
    worst = max((c["level"] for c in live), key=lambda lv: LEVEL_ORDER.get(lv, 0), default=None)
    return {
        "id": terminal["id"], "name": terminal["name"], "airport": terminal["airport"],
        "description": terminal.get("description"), "capacity": terminal["capacity"],
        "total_people": people, "queue_people": queue,
        "occupancy_pct": round(100 * people / terminal["capacity"], 1) if terminal["capacity"] else 0,
        "avg_density": round(people / area, 2) if area else 0,
        "level": worst, "max_wait_min": max((c["wait_min"] for c in live), default=0),
        "cameras_live": sum(1 for c in cams if c["status"] == "live"), "cameras_total": len(cams),
        "needs_action": any(needs_action(c) for c in cams),
    }


def build_plan(cams: list[dict]) -> dict:
    """Rebalance queues between the checkpoints of one terminal and size extra staffing."""
    live = [c for c in cams if c["status"] != "no_data"]
    if not live:
        return {"status": "no_data", "headline": "Waiting for the first analysed camera frames.", "actions": [],
                "rebalance": None, "waits": {}, "target_camera": None}

    waits = {c["id"]: c["wait_min"] for c in live}
    actions: list[dict] = []
    queues = {c["id"]: c["people_in_queue"] for c in live}
    rebalance = None
    target = min(live, key=lambda c: c["wait_min"])

    if len(live) >= 2:
        src = max(live, key=lambda c: c["wait_min"])
        dst = target
        if src["id"] != dst["id"] and src["wait_min"] - dst["wait_min"] >= 3 and src["wait_min"] >= ref.QUEUE_WAIT_TARGET_MIN * 0.8:
            r_s, r_d = throughput(src), throughput(dst)
            n = (src["people_in_queue"] * r_d - dst["people_in_queue"] * r_s) / (r_s + r_d)
            n = int(max(0, min(round(n), math.floor(0.6 * src["people_in_queue"]))))
            if n >= 3:
                queues[src["id"]] -= n
                queues[dst["id"]] += n
                after = {src["id"]: round(queues[src["id"]] / r_s, 1), dst["id"]: round(queues[dst["id"]] / r_d, 1)}
                rebalance = {"from": src["id"], "to": dst["id"], "people": n, "projected": after}
                actions.append({
                    "type": "REDIRECT",
                    "title": f"Steer the next {n} arriving passengers from {src['name']} to {dst['name']}",
                    "detail": (f"Waits even out at about {max(after.values()):.0f} min "
                               f"({src['wait_min']:.0f} min and {dst['wait_min']:.0f} min today)."),
                    "from_camera": src["id"], "to_camera": dst["id"], "people": n,
                    "before": {src["id"]: src["wait_min"], dst["id"]: dst["wait_min"]}, "after": after,
                })

    for c in live:
        q = queues[c["id"]]
        proj = wait_minutes(q, c)
        if proj > ref.QUEUE_WAIT_TARGET_MIN:
            extra = math.ceil(q / (ref.QUEUE_WAIT_TARGET_MIN * c["rate_per_point"])) - c["service_points"]
            if extra > 0:
                actions.append({
                    "type": "OPEN_LANES",
                    "title": f"Open {extra} more lane{'s' if extra > 1 else ''} at {c['name']}",
                    "detail": (f"Brings the wait from about {proj:.0f} min to "
                               f"{wait_minutes(q, c, extra):.0f} min (target {ref.QUEUE_WAIT_TARGET_MIN} min)."),
                    "from_camera": c["id"], "to_camera": None, "people": 0,
                    "before": {c["id"]: proj}, "after": {c["id"]: wait_minutes(q, c, extra)}, "extra_points": extra,
                })

    if any(needs_action(c) for c in live):
        status = "action"
        headline = (f"{max(live, key=lambda c: c['wait_min'])['name']} has the longest queue "
                    f"(about {max(waits.values()):.0f} min). Rerouting is recommended.")
    elif any(LEVEL_ORDER.get(c["level"], 0) >= LEVEL_ORDER["MODERATE"] and c["wait_min"] >= ref.QUEUE_WAIT_TARGET_MIN for c in live):
        status, headline = "watch", "Queues are building. Keep monitoring."
    else:
        status, headline = "normal", "Crowd levels are normal. No rerouting needed."
    return {"status": status, "headline": headline, "actions": actions, "rebalance": rebalance, "waits": waits,
            "target_camera": target["id"], "target_wait_min": target["wait_min"]}


def risk_slack(minutes_to_departure: float, wait_min: float) -> float:
    """Spare minutes before the gate closes after clearing a queue of ``wait_min`` (negative means likely to miss)."""
    return minutes_to_departure - ref.GATE_CLOSE_BUFFER_MIN - wait_min
