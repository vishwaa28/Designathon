"""Crowd analytics: turns head counts from camera frames into density, queue wait and a rerouting plan.

Everything here is deterministic and unit-testable. The vision model only supplies the counts; the floor
area, service rates and thresholds come from ``app.data.reference`` (CAMERAS, DENSITY_BANDS_BY_KIND, ...).

Rerouting strategy (``build_plan``)
-----------------------------------
Moving people who are already queuing is slow and unpopular, so the plan steers the passengers who have *not
yet arrived* at security:

1. **Expected arrivals.** Each departure sends its passengers to security spread evenly between
   ``ARRIVE_EARLY_MIN`` and ``GATE_CLOSE_BUFFER_MIN`` minutes before it leaves. Summing that over the next
   ``HORIZON_MIN`` minutes gives the inflow. When the concourse camera sees more people than that, the
   camera count wins (they are already on their way).
2. **Water-filling allocation.** The inflow is split across the checkpoints so that every checkpoint that gets
   anyone ends up with the same wait (queue + share) / screening rate. That is the split that minimises the
   longest wait.
3. **Extra lanes.** If the longest wait is still above the target, lanes are opened one at a time where they
   bring it down the most, up to ``MAX_EXTRA_LANES`` per checkpoint.
4. **Fast-track.** Flights that would still leave under ``TIGHT_SLACK_MIN`` spare minutes are sent through the
   fast-track lane; every flight gets a checkpoint and a "be at security by" time.
5. **Crowd control.** A crowded concourse or gate lounge gets its own action.
"""
from __future__ import annotations

import statistics
from collections import Counter

from app.data import reference as ref

MOVEMENTS = ("flowing", "slow", "stationary")
SMOOTHING_SAMPLES = 5            # observations in the rolling median
SMOOTHING_WINDOW_S = 180         # ignore observations older than this relative to the newest
STALE_AFTER_S = 120              # no new frame for this long -> the tile is marked stale
MAX_PEOPLE = 600
HORIZON_MIN = 15                 # look-ahead for expected arrivals
MIN_PLANNING_DEMAND = 30         # people used to size the split when almost nobody is expected
TIGHT_SLACK_MIN = 15             # flights below this slack (after the plan) get the fast-track lane
LEVEL_ORDER = {name: i for i, (name, _) in enumerate(ref.DENSITY_BANDS)}


def kind_of(cam: dict) -> str:
    return cam.get("kind", "security")


def density_level(density: float, kind: str = "security") -> str:
    bands = ref.DENSITY_BANDS_BY_KIND.get(kind, ref.DENSITY_BANDS)
    level = bands[0][0]
    for name, floor in bands:
        if density >= floor:
            level = name
    return level


def throughput(cam: dict) -> float:
    """Passengers processed per minute with the configured number of open service points."""
    return max(0.1, (cam.get("service_points") or 0) * (cam.get("rate_per_point") or 0))


def wait_minutes(queue: int, cam: dict, extra_points: int = 0) -> float:
    rate = max(0.1, ((cam.get("service_points") or 0) + extra_points) * (cam.get("rate_per_point") or 0))
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
    wait = wait_minutes(obs["people_in_queue"], cam) if kind_of(cam) == "security" else 0.0
    return {"density": density, "level": density_level(density, kind_of(cam)), "wait_min": wait}


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
    if state["status"] == "no_data":
        return False
    if LEVEL_ORDER.get(state["level"], 0) >= LEVEL_ORDER["HIGH"]:
        return True
    return kind_of(state) == "security" and state["wait_min"] >= ref.QUEUE_WAIT_ALERT_MIN


def rollup(terminal: dict, cams: list[dict]) -> dict:
    live = [c for c in cams if c["status"] != "no_data"]
    security = [c for c in live if kind_of(c) == "security"]
    people = sum(c["people_total"] for c in live)
    peak = max(live, key=lambda c: (LEVEL_ORDER.get(c["level"], 0), c["density"]), default=None)
    return {
        "id": terminal["id"], "name": terminal["name"], "airport": terminal["airport"],
        "description": terminal.get("description"), "capacity": terminal["capacity"],
        "total_people": people, "queue_people": sum(c["people_in_queue"] for c in security),
        "occupancy_pct": round(100 * people / terminal["capacity"], 1) if terminal["capacity"] else 0,
        "peak_density": peak["density"] if peak else 0, "peak_camera": peak["name"] if peak else None,
        "level": peak["level"] if peak else None,
        "max_wait_min": max((c["wait_min"] for c in security), default=0),
        "cameras_live": sum(1 for c in cams if c["status"] == "live"), "cameras_total": len(cams),
        "needs_action": any(needs_action(c) for c in cams),
    }


# ---- planning --------------------------------------------------------------------------
def schedule_inflow(flights: list[dict], horizon: int = HORIZON_MIN) -> float:
    """Passengers expected to reach security within ``horizon`` minutes, from the departures that are coming up."""
    spread = ref.ARRIVE_EARLY_MIN - ref.GATE_CLOSE_BUFFER_MIN
    total = 0.0
    for f in flights:
        m = f["minutes_to_departure"]
        start, end = max(0.0, m - ref.ARRIVE_EARLY_MIN), m - ref.GATE_CLOSE_BUFFER_MIN
        overlap = min(end, horizon) - start
        if overlap > 0:
            total += f["passengers"] * overlap / spread
    return total


def _allocate(points: list[dict], demand: float) -> dict[str, float]:
    """Split ``demand`` people so every checkpoint that receives anyone ends with the same wait (water-filling)."""
    lo, hi = 0.0, max((p["queue"] + demand) / p["rate"] for p in points)
    for _ in range(60):
        mid = (lo + hi) / 2
        need = sum(max(0.0, mid * p["rate"] - p["queue"]) for p in points)
        lo, hi = (mid, hi) if need < demand else (lo, mid)
    return {p["id"]: max(0.0, hi * p["rate"] - p["queue"]) for p in points}


def _worst_wait(points: list[dict], shares: dict[str, float]) -> float:
    return max((p["queue"] + shares[p["id"]]) / p["rate"] for p in points)


def _plan_lanes(points: list[dict], demand: float) -> tuple[dict[str, float], dict[str, int]]:
    """Allocate demand, then open lanes one at a time where they cut the longest wait the most."""
    extra = {p["id"]: 0 for p in points}
    shares = _allocate(points, demand)
    while _worst_wait(points, shares) > ref.QUEUE_WAIT_TARGET_MIN:
        best = None
        for p in points:
            if extra[p["id"]] >= ref.MAX_EXTRA_LANES:
                continue
            trial = [{**q, "rate": q["rate"] + (q["per_point"] if q["id"] == p["id"] else 0)} for q in points]
            w = _worst_wait(trial, _allocate(trial, demand))
            if best is None or w < best[0] - 1e-9:
                best = (w, p["id"])
        if best is None or best[0] >= _worst_wait(points, shares) - 0.05:
            break
        extra[best[1]] += 1
        for p in points:
            if p["id"] == best[1]:
                p["rate"] += p["per_point"]
        shares = _allocate(points, demand)
    return shares, extra


def _flight_guidance(flights: list[dict], cps: list[dict], baseline: float, projected: float) -> dict[str, dict]:
    """Per departure: which checkpoint and lane to use and how many minutes from now to be at security."""
    by_wait = min(cps, key=lambda c: (c["wait_after_min"], -c["share_pct"]))
    fast = [c for c in cps if c["fast_track"]]
    out = {}
    for f in flights:
        m = f["minutes_to_departure"]
        slack_now = m - ref.GATE_CLOSE_BUFFER_MIN - baseline
        slack_after = m - ref.GATE_CLOSE_BUFFER_MIN - projected
        priority = slack_after < TIGHT_SLACK_MIN and bool(fast)
        target = min(fast, key=lambda c: c["wait_after_min"]) if priority else by_wait
        wait = max(2.0, ref.FAST_TRACK_FACTOR * target["wait_after_min"]) if priority else target["wait_after_min"]
        out[f["trip_id"]] = {
            "checkpoint_id": target["camera_id"], "checkpoint": target["name"],
            "lane": target["alternate"] if priority else None, "priority": priority,
            "expected_wait_min": round(wait, 1),
            "arrive_in_min": int(m - ref.GATE_CLOSE_BUFFER_MIN - wait - ref.SAFETY_MARGIN_MIN),
            "slack_now_min": int(slack_now),
            "slack_after_min": int(m - ref.GATE_CLOSE_BUFFER_MIN - (wait if priority else projected)),
        }
    return out


def build_plan(cams: list[dict], flights: list[dict] | None = None) -> dict:
    """Rebalance arrivals between the checkpoints of one terminal. See the module docstring for the method."""
    flights = flights or []
    live = [c for c in cams if c["status"] != "no_data"]
    security = [c for c in live if kind_of(c) == "security"]
    others = [c for c in live if kind_of(c) != "security"]
    if not security:
        return {"status": "no_data", "headline": "Waiting for the first checkpoint counts.", "actions": [],
                "checkpoints": [], "flights": {}, "waits": {}, "target_camera": None, "inflow": None, "outlook": None}

    points = [{"id": c["id"], "queue": c["people_in_queue"], "rate": throughput(c), "per_point": c["rate_per_point"]}
              for c in security]
    sched = schedule_inflow(flights)
    in_concourse = sum(c["people_in_queue"] for c in others if kind_of(c) == "concourse")
    demand = max(sched, float(in_concourse))
    source = "camera" if in_concourse > sched else "schedule"
    planning = max(demand, float(MIN_PLANNING_DEMAND))

    even = {p["id"]: planning / len(points) for p in points}
    baseline = _worst_wait(points, even)
    shares, extra = _plan_lanes([dict(p) for p in points], planning)

    cps = []
    for c, p in zip(security, points):
        e = extra[c["id"]]
        rate = p["rate"] + e * p["per_point"]
        cps.append({
            "camera_id": c["id"], "name": c["name"], "fast_track": bool(c.get("fast_track")), "alternate": c.get("alternate"),
            "queue": c["people_in_queue"], "lanes": c["service_points"], "extra_lanes": e,
            "wait_now_min": c["wait_min"], "share_pct": round(100 * shares[c["id"]] / planning),
            "arrivals": int(round(shares[c["id"]] * demand / planning)),
            "even_wait_min": round((p["queue"] + even[c["id"]]) / p["rate"], 1),
            "wait_after_min": round((p["queue"] + shares[c["id"]]) / rate, 1),
        })
    # Rounded shares must add up to 100
    drift = 100 - sum(c["share_pct"] for c in cps)
    if drift:
        max(cps, key=lambda c: c["share_pct"])["share_pct"] += drift
    projected = max(c["wait_after_min"] for c in cps)
    guidance = _flight_guidance(flights, cps, baseline, projected)
    best = min(cps, key=lambda c: (c["wait_after_min"], -c["share_pct"]))

    actions: list[dict] = []
    lead = max(cps, key=lambda c: c["share_pct"])
    if len(cps) > 1 and max(abs(c["share_pct"] - 100 / len(cps)) for c in cps) >= 15:
        split = ", ".join(f"{c['name']} {c['share_pct']}%" for c in sorted(cps, key=lambda c: -c["share_pct"]))
        actions.append({
            "type": "DIRECT", "title": f"Guide new arrivals: {split}",
            "detail": (f"Use signage, announcements and app prompts for the {int(round(demand))} passengers expected in the next "
                       f"{HORIZON_MIN} min ({'seen on the concourse camera' if source == 'camera' else 'from the departure schedule'}). "
                       f"An even split would leave the longest wait at {baseline:.0f} min."),
            "impact_min": round(baseline - _worst_wait(points, shares), 1), "owner": "Terminal control and signage",
        })
    for c in cps:
        if c["extra_lanes"]:
            actions.append({
                "type": "OPEN_LANES", "title": f"Open {c['extra_lanes']} more lane{'s' if c['extra_lanes'] > 1 else ''} at {c['name']}",
                "detail": f"{c['lanes']} lanes become {c['lanes'] + c['extra_lanes']}. Its wait drops to about {c['wait_after_min']:.0f} min.",
                "impact_min": None, "owner": "Security duty manager",
            })
    prio = [f for f in flights if guidance[f["trip_id"]]["priority"]]
    if prio:
        names = ", ".join(f["number"] for f in prio[:4]) + (f" and {len(prio) - 4} more" if len(prio) > 4 else "")
        cp = guidance[prio[0]["trip_id"]]
        actions.append({
            "type": "PRIORITY", "title": f"Fast-track {len(prio)} tight departure{'s' if len(prio) > 1 else ''}: {names}",
            "detail": (f"These flights keep under {TIGHT_SLACK_MIN} spare minutes even after rebalancing. "
                       f"Send them to the {cp['lane'] or 'fast-track lane'} at {cp['checkpoint']} and page the passengers."),
            "impact_min": None, "owner": "Gate and customer service",
        })
    for c in others:
        if LEVEL_ORDER.get(c["level"], 0) < LEVEL_ORDER["HIGH"]:
            continue
        if kind_of(c) == "concourse":
            actions.append({
                "type": "CROWD_CONTROL", "title": f"{c['name']} is crowded ({c['density']:.2f} people per m²)",
                "detail": "Deploy marshals to keep the stream moving and meter entry to the security halls. Repeat the checkpoint guidance every few minutes.",
                "impact_min": None, "owner": "Terminal operations",
            })
        else:
            seats = c.get("seats")
            fill = f" ({round(100 * c['people_total'] / seats)}% of {seats} seats)" if seats else ""
            actions.append({
                "type": "CROWD_CONTROL", "title": f"{c['name']} is crowded{fill}",
                "detail": "Open adjacent seating, move boarding to zone-by-zone calls and hold late arrivals at the next gate area.",
                "impact_min": None, "owner": "Gate operations",
            })

    critical = any(LEVEL_ORDER.get(c["level"], 0) >= LEVEL_ORDER["CRITICAL"] for c in others)
    high = any(LEVEL_ORDER.get(c["level"], 0) >= LEVEL_ORDER["HIGH"] for c in others)
    if baseline >= ref.QUEUE_WAIT_ALERT_MIN or any(needs_action(c) for c in security) or critical:
        status = "action"
        headline = (f"Unguided, the longest security wait would reach about {baseline:.0f} min. "
                    f"Guiding arrivals{' and opening lanes' if any(c['extra_lanes'] for c in cps) else ''} "
                    f"brings it to about {projected:.0f} min.")
    elif baseline >= ref.QUEUE_WAIT_TARGET_MIN * 0.8 or high:
        status, headline = "watch", f"Queues are building (about {baseline:.0f} min if unguided). Keep monitoring."
    else:
        status, headline = "normal", "Crowd levels are normal. No rerouting needed."
    return {
        "status": status, "headline": headline, "actions": actions, "checkpoints": cps, "flights": guidance,
        "inflow": {"expected": int(round(demand)), "horizon_min": HORIZON_MIN, "source": source,
                   "from_schedule": int(round(sched)), "on_concourse": in_concourse},
        "outlook": {"unguided_wait_min": round(baseline, 1), "planned_wait_min": projected,
                    "saved_min": round(max(0.0, baseline - projected), 1)},
        "waits": {c["id"]: c["wait_min"] for c in security},
        "target_camera": best["camera_id"], "target_wait_min": best["wait_after_min"],
    }


def risk_slack(minutes_to_departure: float, wait_min: float) -> float:
    """Spare minutes before the gate closes after clearing a queue of ``wait_min`` (negative means likely to miss)."""
    return minutes_to_departure - ref.GATE_CLOSE_BUFFER_MIN - wait_min
