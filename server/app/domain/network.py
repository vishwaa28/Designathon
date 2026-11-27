"""Network calculations: disruption scoping, delay propagation, crew legality and passenger impact."""
from __future__ import annotations

from datetime import datetime

from app.core.utils import add_min, minutes_between, now, parse_dt
from app.data import reference as ref
from app.data.store import store

MIN_TURN = 35
MIN_CONNECTION = 60
CREW_RELEASE_MIN = 30
RESERVE_FALLBACK = {
    "CJB": "MAA", "IXM": "MAA", "TRZ": "MAA", "TRV": "COK", "IXE": "BLR", "VGA": "HYD", "TIR": "MAA",
    "GOI": "BOM", "PNQ": "BOM", "CCU": "DEL",
}


def reserve_base(node: str) -> str:
    return node if node in store.reserves else RESERVE_FALLBACK.get(node, node)


def min_connection(arr_trip: dict, dep_trip: dict) -> int:
    return MIN_CONNECTION


def primary_delays(scope: dict, end: datetime | None = None) -> dict[str, int]:
    """Total delay (minutes vs schedule) caused directly by the disruption if nothing is done."""
    start = parse_dt(scope["start"])
    end = end or parse_dt(scope["end"])
    ref_time = now()
    out: dict[str, int] = {}
    kind = scope["type"]

    if kind == "AIRPORT_CLOSURE":
        node = scope["node"]
        deps = sorted(
            (t for t in store.trips.values()
             if not t["cancelled"] and t["origin"] == node
             and start <= store.est_dep(t) < end and store.est_dep(t) >= ref_time),
            key=store.est_dep,
        )
        for i, t in enumerate(deps):
            out[t["id"]] = max(t["delay_min"], minutes_between(t["sched_dep"], add_min(end, 5 + i * 4)))
        arrs = sorted(
            (t for t in store.trips.values()
             if not t["cancelled"] and t["destination"] == node
             and start <= store.est_arr(t) < end and t["id"] not in out and store.est_arr(t) >= ref_time),
            key=store.est_arr,
        )
        for i, t in enumerate(arrs):
            out[t["id"]] = max(t["delay_min"], minutes_between(t["sched_arr"], add_min(end, 10 + i * 3)))

    elif kind == "VEHICLE_GROUNDED":
        for tid in store.rotations.get(scope["vehicle_id"], []):
            t = store.trips[tid]
            if t["cancelled"] or store.est_dep(t) < start:
                continue
            out[tid] = max(t["delay_min"], minutes_between(t["sched_dep"], end))
            break
    return {k: v for k, v in out.items() if v > 0}


def scoped_trip_ids(scope: dict, end: datetime | None = None) -> list[str]:
    """Trips physically inside the disruption scope (used by strategies)."""
    end = end or parse_dt(scope["end"])
    if scope["type"] == "VEHICLE_GROUNDED":
        start = parse_dt(scope["start"])
        return [tid for tid in store.rotations.get(scope["vehicle_id"], [])
                if not store.trips[tid]["cancelled"] and store.est_dep(store.trips[tid]) >= start]
    return list(primary_delays(scope, end).keys())


def propagate(primary: dict[str, int], cancels: set[str] | frozenset = frozenset()) -> dict[str, int]:
    """Push delays down each aircraft rotation, absorbing what turnaround slack allows."""
    vehicles = {store.trips[t]["vehicle_id"] for t in primary} | {store.trips[t]["vehicle_id"] for t in cancels}
    result: dict[str, int] = {}
    for vid in vehicles:
        prev: tuple[dict, int] | None = None
        for tid in store.rotations.get(vid, []):
            if tid in cancels:
                continue
            t = store.trips[tid]
            own = primary.get(tid, t["delay_min"])
            carried = 0
            if prev:
                p, pd = prev
                slack = minutes_between(p["sched_arr"], t["sched_dep"]) - MIN_TURN
                carried = max(0, pd - max(0, slack))
            d = max(own, carried)
            if d > 0:
                result[tid] = d
            prev = (t, d)
    return result


def crew_breaches(delays: dict[str, int], cancels: set[str] | frozenset = frozenset()) -> list[dict]:
    touched = {store.trips[t]["pairing_id"] for t in delays} | {store.trips[t]["pairing_id"] for t in cancels}
    out = []
    for pid in touched:
        if not pid:
            continue
        p = store.pairings[pid]
        active = [t for t in p["trip_ids"] if t not in cancels and not store.trips[t]["cancelled"]]
        if not active:
            continue
        last = store.trips[active[-1]]
        end = add_min(last["sched_arr"], delays.get(last["id"], last["delay_min"]) + CREW_RELEASE_MIN)
        duty_h = (end - p["duty_start"]).total_seconds() / 3600
        members = []
        for cid in p["crew_ids"]:
            c = store.crew[cid]
            if duty_h > c["duty_limit_h"]:
                members.append({
                    "id": cid, "name": c["name"], "role": c["role"],
                    "role_label": ref.ROLE_LABELS[c["role"]], "limit_h": c["duty_limit_h"],
                    "excess_min": int((duty_h - c["duty_limit_h"]) * 60),
                })
        if members:
            # Replacement is needed before the first leg that would end beyond the limit.
            swap_trip = active[-1]
            for tid in active:
                t = store.trips[tid]
                t_end = add_min(t["sched_arr"], delays.get(tid, t["delay_min"]) + CREW_RELEASE_MIN)
                if (t_end - p["duty_start"]).total_seconds() / 3600 > min(m["limit_h"] for m in members):
                    swap_trip = tid
                    break
            swap_node = store.trips[swap_trip]["origin"]
            out.append({
                "pairing_id": pid,
                "swap_trip_id": swap_trip,
                "swap_trip": store.trips[swap_trip]["number"],
                "swap_airport": ref.display_code(swap_node),
                "reserve_base": reserve_base(swap_node),
                "trips": [store.trips[t]["number"] for t in active],
                "projected_duty_h": round(duty_h, 2),
                "members": members,
            })
    out.sort(key=lambda b: -b["projected_duty_h"])
    return out


def pax_effects(delays: dict[str, int], cancels: set[str] | frozenset = frozenset(),
                threshold: int = 15) -> dict[str, dict]:
    """Per-passenger effect: worst delay, cancelled leg, missed connection."""
    candidates: set[str] = set()
    for tid in set(delays) | set(cancels):
        candidates |= store.pax_by_trip.get(tid, set())
    out: dict[str, dict] = {}
    for pid in candidates:
        p = store.passengers[pid]
        legs = p["legs"]
        worst, worst_leg, cancelled_leg, missed = 0, None, None, None
        for tid in legs:
            if tid in cancels or store.trips[tid]["cancelled"]:
                cancelled_leg = cancelled_leg or tid
                continue
            d = delays.get(tid, store.trips[tid]["delay_min"])
            if d > worst:
                worst, worst_leg = d, tid
        for a, b in zip(legs, legs[1:]):
            if a in cancels or b in cancels:
                continue
            ta, tb = store.trips[a], store.trips[b]
            arr = add_min(ta["sched_arr"], delays.get(a, ta["delay_min"]))
            dep = add_min(tb["sched_dep"], delays.get(b, tb["delay_min"]))
            if minutes_between(arr, dep) < min_connection(ta, tb):
                missed = (a, b)
                break
        if worst >= threshold or cancelled_leg or missed:
            out[pid] = {"delay": worst, "delay_leg": worst_leg, "cancelled_leg": cancelled_leg, "missed": missed}
    return out
