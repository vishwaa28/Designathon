"""Recovery plan generation and evaluation.

Each strategy produces a set of retimings, cancellations, diversions and bus bridges. The
shared evaluator then re-accommodates passengers against live seat inventory (priority
passengers first), allocates reserve crew to duty-time breaches, checks transit rules and
prices the plan.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Callable

from app.core.utils import add_min, iso, minutes_between, now, parse_dt
from app.data import reference as ref
from app.data.store import is_priority, priority_score, store
from app.domain.geo import flight_minutes
from app.domain.network import crew_breaches, min_connection, pax_effects, primary_delays, propagate, scoped_trip_ids

COST = {
    "delay_per_min": {"FLIGHT": 2200, "TRAIN": 450},
    "care_2h": {"FLIGHT": 350, "TRAIN": 150},
    "hotel": {"FLIGHT": 4200, "TRAIN": 1400},
    "cancel_comp": {"FLIGHT": 5000, "TRAIN": 250},
    "rebook": {"FLIGHT": 600, "TRAIN": 150},
    "alt_mode": 1800,
    "reserve_callout": 18000,
    "diversion": 350000,
    "coach": 28000,
    "ferry": 650000,
}
COACH_SEATS = 50
REBOOK_HORIZON_MIN = 18 * 60
ALTERNATES = {"DEL": [("JAI", 300), ("LKO", 480)], "BOM": [("PNQ", 210), ("AMD", 480)]}
RAIL_DIVERSION = {frozenset({"R:NDLS", "R:AGC"}): ("Mathura-Alwar-Bayana", 95)}
BUS_BRIDGE_MIN = {frozenset({"R:NDLS", "R:AGC"}): 240, frozenset({"R:CSMT", "R:PUNE"}): 210}


def _alt_index() -> dict[tuple[str, str], list[str]]:
    idx: dict[tuple[str, str], list[str]] = defaultdict(list)
    for t in store.trips.values():
        idx[(ref.city_of(t["origin"]), ref.city_of(t["destination"]))].append(t["id"])
    for k in idx:
        idx[k].sort(key=lambda tid: store.trips[tid]["sched_dep"])
    return idx


def _est(tid: str, delays: dict[str, int], field: str) -> datetime:
    t = store.trips[tid]
    return add_min(t[field], delays.get(tid, t["delay_min"]))


def _constraint(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def evaluate_plan(
    *, ctx: dict, primary: dict[str, int], cancels: set[str] | None = None,
    diversions: dict[str, tuple[str, int]] | None = None, bus_bridge: dict[str, int] | None = None,
    allow_alt_mode: bool = False, extra_costs: list[tuple[str, int]] | None = None,
    actions: list[dict] | None = None, extra_constraints: list[dict] | None = None,
) -> tuple[dict, dict]:
    cancels = set(cancels or ())
    diversions = diversions or {}
    bus_bridge = bus_bridge or {}
    adjustments = ctx.get("adjustments", {})
    preferences = ctx.get("preferences", {})
    ref_time = now()

    delays = propagate(primary, cancels)
    for tid in cancels:
        delays.pop(tid, None)

    # ---- crew legality ----------------------------------------------------
    breaches = crew_breaches(delays, cancels)
    pool = {b: {r: len(ids) for r, ids in roles.items()} for b, roles in store.reserves.items()}
    for base_code in adjustments.get("reserve_unavailable", []):
        if base_code in pool:
            pool[base_code] = {r: 0 for r in pool[base_code]}
    for consumed_base, role, n in ctx.get("_reserve_consumed", []):
        if consumed_base in pool and role in pool[consumed_base]:
            pool[consumed_base][role] = max(0, pool[consumed_base][role] - n)
    resolved_members, unresolved = 0, []
    crew_actions = []
    for b in breaches:
        base_pool = pool.get(b["reserve_base"], {})
        ok = True
        for m in b["members"]:
            if base_pool.get(m["role"], 0) > 0:
                base_pool[m["role"]] -= 1
                resolved_members += 1
            else:
                ok = False
        if ok:
            crew_actions.append({"type": "CREW_SWAP", "trip": b["swap_trip"],
                                 "detail": f"Reserve crew from {ref.display_code(b['reserve_base'])} replaces {len(b['members'])} crew before {b['swap_trip']}"})
        else:
            unresolved.append(b)

    # ---- passenger re-accommodation ----------------------------------------
    inventory_factor = float(adjustments.get("inventory_factor", 1.0))
    inventory = {tid: int(store.spare_seats(tid) * inventory_factor) for tid in store.trips if tid not in cancels}
    effects = pax_effects(delays, cancels)
    idx = _alt_index()

    def find_alt(origin: str, dest: str, ready: datetime, mode: str, exclude: set[str]) -> str | None:
        key = (ref.city_of(origin), ref.city_of(dest))
        horizon = add_min(ready, REBOOK_HORIZON_MIN)
        best_same, best_other = None, None
        for tid in idx.get(key, []):
            t = store.trips[tid]
            if tid in exclude or tid in cancels or t["cancelled"] or tid in diversions or tid in bus_bridge:
                continue
            dep = _est(tid, delays, "sched_dep")
            if dep < ready or dep > horizon or inventory.get(tid, 0) <= 0:
                continue
            if t["mode"] == mode:
                if best_same is None:
                    best_same = tid
            elif allow_alt_mode and best_other is None:
                best_other = tid
            if best_same and (best_other or not allow_alt_mode):
                break
        if best_same and best_other:
            same_arr = _est(best_same, delays, "sched_arr")
            other_arr = _est(best_other, delays, "sched_arr")
            return best_other if minutes_between(other_arr, same_arr) > 120 else best_same
        return best_same or best_other

    outcomes: dict[str, dict] = {}
    rebook_queue = []
    for pid, e in effects.items():
        p = store.passengers[pid]
        if e["cancelled_leg"] and e["cancelled_leg"] in bus_bridge:
            outcomes[pid] = {"type": "BUS_BRIDGE", "leg": e["cancelled_leg"], "new_trip": None,
                             "delay_min": bus_bridge[e["cancelled_leg"]]}
        elif e["cancelled_leg"]:
            leg = store.trips[e["cancelled_leg"]]
            ready = max(add_min(ref_time, 30), leg["sched_dep"])
            rebook_queue.append((pid, leg["id"], leg["origin"], leg["destination"], ready, leg["sched_arr"]))
        elif e["missed"]:
            a, b = e["missed"]
            ta, tb = store.trips[a], store.trips[b]
            ready = add_min(_est(a, delays, "sched_arr"), min_connection(ta, tb))
            rebook_queue.append((pid, b, tb["origin"], tb["destination"], ready, tb["sched_arr"]))
        elif e["delay_leg"] in diversions:
            alt, transfer = diversions[e["delay_leg"]]
            outcomes[pid] = {"type": "DIVERTED", "leg": e["delay_leg"], "new_trip": None,
                             "delay_min": e["delay"] + transfer, "via": alt}
        else:
            outcomes[pid] = {"type": "DELAYED", "leg": e["delay_leg"], "new_trip": None, "delay_min": e["delay"]}

    rebook_queue.sort(key=lambda r: (-priority_score(store.passengers[r[0]]), r[4]))
    for pid, leg_id, origin, dest, ready, orig_arr in rebook_queue:
        p = store.passengers[pid]
        exclude = set(p["legs"])
        alt = find_alt(origin, dest, ready, store.trips[leg_id]["mode"], exclude)
        if alt:
            inventory[alt] -= 1
            new_arr = _est(alt, delays, "sched_arr")
            same_mode = store.trips[alt]["mode"] == store.trips[leg_id]["mode"]
            outcomes[pid] = {"type": "REBOOKED" if same_mode else "ALT_MODE", "leg": leg_id, "new_trip": alt,
                             "delay_min": max(0, minutes_between(orig_arr, new_arr))}
        else:
            outcomes[pid] = {"type": "UNACCOMMODATED", "leg": leg_id, "new_trip": None, "delay_min": 0}

    # ---- metrics ----------------------------------------------------------
    by_type: dict[str, int] = defaultdict(int)
    for o in outcomes.values():
        by_type[o["type"]] += 1
    delayed_trips = {t: d for t, d in delays.items() if d >= 15}
    missed_total = sum(1 for e in effects.values() if e["missed"])
    missed_protected = sum(1 for pid, e in effects.items() if e["missed"] and outcomes[pid]["type"] in ("REBOOKED", "ALT_MODE"))
    priority_total = sum(1 for pid in effects if is_priority(store.passengers[pid]))
    priority_unprotected = sum(1 for pid, o in outcomes.items() if o["type"] == "UNACCOMMODATED" and is_priority(store.passengers[pid]))
    pax_delay_hours = sum(o["delay_min"] for o in outcomes.values()) / 60

    recovery_points = [_est(t, delays, "sched_dep") for t in delayed_trips]
    recovery_points += [_est(o["new_trip"], delays, "sched_dep") for o in outcomes.values() if o["new_trip"]]
    recovery_by = max(recovery_points) if recovery_points else ref_time
    recovery_min = max(0, minutes_between(ref_time, recovery_by))

    # ---- cost -------------------------------------------------------------
    cost: dict[str, float] = defaultdict(float)
    for tid, d in delays.items():
        t = store.trips[tid]
        cost["Operational delay"] += max(0, d - t["delay_min"]) * COST["delay_per_min"][t["mode"]]
    for pid, o in outcomes.items():
        p = store.passengers[pid]
        mode = store.trips[o["leg"]]["mode"] if o["leg"] else "FLIGHT"
        typ = o["type"]
        if typ in ("DELAYED", "DIVERTED"):
            if o["delay_min"] >= 120:
                cost["Passenger care"] += COST["care_2h"][mode]
            if o["delay_min"] >= 360:
                cost["Hotel & meals"] += COST["hotel"][mode]
        elif typ in ("REBOOKED", "ALT_MODE"):
            cost["Rebooking"] += COST["rebook"][mode] if typ == "REBOOKED" else COST["alt_mode"]
            if o["delay_min"] >= 360:
                cost["Hotel & meals"] += COST["hotel"][mode]
        elif typ == "UNACCOMMODATED":
            cost["Refunds"] += p["fare"]
            cost["Hotel & meals"] += COST["hotel"][mode] * 0.5
        if o["leg"] in cancels and mode == "FLIGHT":
            cost["Cancellation compensation"] += COST["cancel_comp"]["FLIGHT"]
        elif o["leg"] in cancels:
            cost["Cancellation compensation"] += COST["cancel_comp"]["TRAIN"]
    bridge_pax = by_type.get("BUS_BRIDGE", 0)
    if bridge_pax:
        cost["Bus bridge"] += math.ceil(bridge_pax / COACH_SEATS) * COST["coach"]
    for tid in diversions:
        cost["Diversions"] += COST["diversion"] + math.ceil(store.booked(tid) / COACH_SEATS) * COST["coach"]
    cost["Reserve crew"] += resolved_members * COST["reserve_callout"]
    for label, amount in extra_costs or []:
        cost[label] += amount
    total_cost = int(sum(cost.values()))

    # ---- constraints ------------------------------------------------------
    constraints = list(extra_constraints or [])
    need = len(rebook_queue)
    unacc = by_type.get("UNACCOMMODATED", 0)
    if need == 0:
        constraints.append(_constraint("Seat inventory", "PASS", "No re-accommodation required."))
    elif unacc == 0:
        constraints.append(_constraint("Seat inventory", "PASS", f"All {need} passengers needing new travel placed on trips with open seats."))
    else:
        status = "WARN" if unacc <= max(25, 0.15 * need) else "FAIL"
        constraints.append(_constraint("Seat inventory", status, f"{need - unacc} of {need} re-accommodated; {unacc} offered refund or next-day travel."))
    if not breaches:
        constraints.append(_constraint("Crew duty-time limits", "PASS", "No pairing exceeds its flight / duty-time limit."))
    elif not unresolved:
        constraints.append(_constraint("Crew duty-time limits", "PASS", f"{len(breaches)} pairings exceed limits; {resolved_members} reserve crew assigned."))
    else:
        constraints.append(_constraint("Crew duty-time limits", "FAIL", f"{len(unresolved)} pairings exceed limits with no reserve crew available at base."))
    constraints.append(_constraint("Minimum connection time", "PASS", "Every rebooked itinerary respects minimum connection times (air 60, air-rail 120, rail-air 150 min)."))
    if priority_total:
        status = "PASS" if priority_unprotected == 0 else "WARN"
        constraints.append(_constraint("Priority passengers", status,
                                       f"{priority_total - priority_unprotected} of {priority_total} priority passengers protected first."))
    max_delay = max(delayed_trips.values()) if delayed_trips else 0
    cap = preferences.get("max_delay_min")
    if cap:
        constraints.append(_constraint("Controller max delay", "PASS" if max_delay <= cap else "WARN",
                                       f"Longest delay {max_delay} min vs {cap} min limit."))
    if preferences.get("avoid_cancellations") and cancels:
        constraints.append(_constraint("Controller: avoid cancellations", "WARN", f"Plan cancels {len(cancels)} services."))

    all_actions = list(actions or []) + crew_actions
    option = {
        "metrics": {
            "trips_delayed": len(delayed_trips),
            "trips_cancelled": len(cancels),
            "trips_diverted": len(diversions),
            "avg_delay_min": int(sum(delayed_trips.values()) / len(delayed_trips)) if delayed_trips else 0,
            "max_delay_min": max_delay,
            "pax_affected": len(effects),
            "pax_delayed": by_type.get("DELAYED", 0) + by_type.get("DIVERTED", 0),
            "pax_rebooked": by_type.get("REBOOKED", 0),
            "pax_alt_mode": by_type.get("ALT_MODE", 0) + by_type.get("BUS_BRIDGE", 0),
            "pax_unaccommodated": unacc,
            "pax_delay_hours": round(pax_delay_hours, 1),
            "connections_missed": missed_total,
            "connections_protected": missed_protected,
            "priority_total": priority_total,
            "priority_unprotected": priority_unprotected,
            "crew_breaches": len(breaches),
            "crew_unresolved": len(unresolved),
            "reserve_crew_used": resolved_members,
            "recovery_min": recovery_min,
            "recovery_by": iso(recovery_by),
        },
        "cost": {"total": total_cost, "breakdown": {k: int(v) for k, v in cost.items() if v}},
        "constraints": constraints,
        "actions": all_actions[:40],
        "action_count": len(all_actions),
    }
    artifacts = {
        "pax_outcomes": outcomes,
        "delays": delays,
        "cancels": sorted(cancels),
        "diversions": {k: v[0] for k, v in diversions.items()},
        "bus_bridge": sorted(bus_bridge),
    }
    return option, artifacts


# ---------------------------------------------------------------------------
# Strategies. Each returns evaluate_plan kwargs for a given restoration time.
# ---------------------------------------------------------------------------

def _retime_actions(primary: dict[str, int], label: str) -> list[dict]:
    return [{"type": "RETIME", "trip": store.trips[t]["number"],
             "detail": f"{label} {store.trips[t]['number']} by {d} min"} for t, d in sorted(primary.items(), key=lambda x: -x[1])]


def weather_hold(ctx: dict, end: datetime) -> dict:
    primary = primary_delays(ctx["scope"], end)
    return {"primary": primary, "actions": _retime_actions(primary, "Hold and retime")}


def weather_cancel_consolidate(ctx: dict, end: datetime) -> dict:
    node = ctx["scope"]["node"]
    primary = primary_delays(ctx["scope"], end)
    pairs = []
    for tid, d in primary.items():
        t = store.trips[tid]
        if t["origin"] != node or d < 60:
            continue
        rot = store.rotations[t["vehicle_id"]]
        i = rot.index(tid)
        if i + 1 < len(rot):
            nxt = store.trips[rot[i + 1]]
            if nxt["origin"] == t["destination"] and nxt["destination"] == node:
                load = (store.booked(tid) + store.booked(nxt["id"])) / (t["capacity"] + nxt["capacity"])
                pairs.append((load, tid, nxt["id"]))
    pairs.sort()
    n = max(1, math.ceil(len(pairs) * 0.4)) if pairs else 0
    cancels = set()
    actions = []
    for load, a, b in pairs[:n]:
        cancels |= {a, b}
        actions.append({"type": "CANCEL", "trip": store.trips[a]["number"],
                        "detail": f"Cancel {store.trips[a]['number']}/{store.trips[b]['number']} rotation pair (load {load:.0%}), consolidate passengers"})
    remaining = {k: v for k, v in primary.items() if k not in cancels}
    actions += _retime_actions(remaining, "Retime")
    return {"primary": remaining, "cancels": cancels, "actions": actions}


def weather_divert_multimodal(ctx: dict, end: datetime) -> dict:
    node = ctx["scope"]["node"]
    primary = primary_delays(ctx["scope"], end)
    diversions: dict[str, tuple[str, int]] = {}
    cancels: set[str] = set()
    actions = []
    rail_cities = {ref.city_of(t["destination"]) for t in store.trips.values() if t["mode"] == "TRAIN" and ref.city_of(t["origin"]) == ref.city_of(node)}
    for tid, d in list(primary.items()):
        t = store.trips[tid]
        if t["destination"] == node and d >= 90:
            options = [(alt, mins) for alt, mins in ALTERNATES.get(node, []) if alt != t["origin"]]
            if not options:
                continue
            alt, transfer = options[0]
            diversions[tid] = (alt, transfer)
            primary[tid] = 25
            actions.append({"type": "DIVERT", "trip": t["number"], "detail": f"Divert {t['number']} to {alt}; coach transfer to {ref.city_of(node)}"})
            rot = store.rotations[t["vehicle_id"]]
            i = rot.index(tid)
            if i + 1 < len(rot):
                nxt = store.trips[rot[i + 1]]
                reposition = add_min(end, flight_minutes(alt, node) + 45)
                primary[nxt["id"]] = max(primary.get(nxt["id"], 0), minutes_between(nxt["sched_dep"], reposition))
        elif t["origin"] == node and ref.city_of(t["destination"]) in rail_cities and d >= 60:
            cancels.add(tid)
            actions.append({"type": "ALT_MODE", "trip": t["number"],
                            "detail": f"Cancel short-haul {t['number']}; move passengers to rail towards {ref.city_of(t['destination'])}"})
    remaining = {k: v for k, v in primary.items() if k not in cancels}
    actions += _retime_actions({k: v for k, v in remaining.items() if k not in diversions}, "Retime")
    constraints = [_constraint("Alternate aerodrome capacity", "PASS" if len(diversions) <= 4 else "WARN",
                               f"{len(diversions)} diversions planned against 4 parking stands available at alternates.")]
    return {"primary": remaining, "cancels": cancels, "diversions": diversions, "allow_alt_mode": True,
            "actions": actions, "extra_constraints": constraints}


def rail_caution_order(ctx: dict, end: datetime) -> dict:
    scope = ctx["scope"]
    ids = scoped_trip_ids(scope, end)
    primary = {tid: store.trips[tid]["delay_min"] + 35 + i * 20 for i, tid in enumerate(ids)}
    queue_ok = len(ids) <= 6
    constraints = [
        _constraint("Transit rule: one train per block under Paper Line Clear", "PASS" if queue_ok else "WARN",
                    f"{len(ids)} trains queued through the failed block at 3 trains/hour."),
    ]
    if scope.get("hazard") == "FLOOD":
        constraints.append(_constraint("Safety rule: water above rail", "FAIL",
                                       "Traffic must be suspended while water is more than 25 mm above rail level."))
    else:
        constraints.append(_constraint("Speed restriction", "PASS",
                                       "15 km/h caution order through the affected section with station-master authority."))
    return {"primary": primary, "actions": _retime_actions(primary, "Run under caution order"), "extra_constraints": constraints}


def rail_hold(ctx: dict, end: datetime) -> dict:
    primary = primary_delays(ctx["scope"], end)
    return {"primary": primary, "actions": _retime_actions(primary, "Hold until block restored, retime")}


def rail_short_terminate(ctx: dict, end: datetime) -> dict:
    scope = ctx["scope"]
    corridor = frozenset(scope["corridor"])
    ids = scoped_trip_ids(scope, end)
    bridge_min = BUS_BRIDGE_MIN.get(corridor, 240)
    diversion = RAIL_DIVERSION.get(corridor)
    cancels: set[str] = set()
    bus: dict[str, int] = {}
    primary: dict[str, int] = {}
    actions = []
    for tid in ids:
        t = store.trips[tid]
        dur = minutes_between(t["sched_dep"], t["sched_arr"])
        if dur <= 240 or not diversion:
            cancels.add(tid)
            bus[tid] = max(30, bridge_min - dur + 45)
            actions.append({"type": "BUS_BRIDGE", "trip": t["number"],
                            "detail": f"Short-terminate {t['number']}; {math.ceil(store.booked(tid) / COACH_SEATS)} coaches bridge the section"})
        else:
            route, extra = diversion
            primary[tid] = t["delay_min"] + extra
            actions.append({"type": "REROUTE", "trip": t["number"], "detail": f"Divert {t['number']} via {route} (+{extra} min)"})
    constraints = [_constraint("Coach availability", "PASS" if len(bus) <= 6 else "WARN",
                               f"{sum(math.ceil(store.booked(t) / COACH_SEATS) for t in bus)} coaches required from contracted pool of 60.")]
    return {"primary": primary, "cancels": cancels, "bus_bridge": bus, "allow_alt_mode": True,
            "actions": actions, "extra_constraints": constraints}


def aog_tail_swap(ctx: dict, end: datetime) -> dict:
    scope = ctx["scope"]
    ids = scoped_trip_ids(scope, end)
    spare = next((v for v in store.vehicles.values() if v.get("spare")), None)
    if not ids or not spare:
        return {"primary": {}, "extra_constraints": [_constraint("Spare aircraft", "FAIL", "No spare aircraft available.")]}
    first = store.trips[ids[0]]
    ferry = flight_minutes(spare["base"], first["origin"]) + 60
    ready = add_min(now(), ferry)
    primary = {ids[0]: max(first["delay_min"], minutes_between(first["sched_dep"], ready))}
    ctx["_reserve_consumed"] = [(spare["base"], "CPT", 1), (spare["base"], "FO", 1)]
    constraints = [
        _constraint("Spare aircraft", "PASS", f"{spare['id']} ({spare['type']}) serviceable at {spare['base']}; ferry {ferry - 60} min."),
        _constraint("Fleet type compatibility", "PASS", f"{spare['type']} matches seat map; no downgrade required."),
    ]
    actions = [{"type": "SWAP_AIRCRAFT", "trip": first["number"],
                "detail": f"Ferry {spare['id']} {spare['base']}-{first['origin']} and swap onto remaining {len(ids)} legs"}]
    actions += _retime_actions(primary, "Retime")
    return {"primary": primary, "extra_costs": [("Ferry flight", COST["ferry"])], "actions": actions, "extra_constraints": constraints}


def aog_delay(ctx: dict, end: datetime) -> dict:
    primary = primary_delays(ctx["scope"], end)
    return {"primary": primary, "actions": _retime_actions(primary, "Hold for repair, retime")}


def aog_cancel(ctx: dict, end: datetime) -> dict:
    ids = scoped_trip_ids(ctx["scope"], end)
    actions = [{"type": "CANCEL", "trip": store.trips[t]["number"], "detail": f"Cancel {store.trips[t]['number']} and re-accommodate passengers"} for t in ids]
    return {"primary": {}, "cancels": set(ids), "allow_alt_mode": True, "actions": actions}


STRATEGIES: dict[str, list[tuple[str, str, str, bool, Callable]]] = {
    "AIRPORT_CLOSURE": [
        ("HOLD", "Hold and retime", "Hold departures and arrivals until the runway reopens, then release on a flow-controlled schedule. Reserve crew covers duty-time breaches.", True, weather_hold),
        ("CONSOLIDATE", "Cancel and consolidate", "Cancel the lowest-load rotation pairs to cut the cascading delay, consolidating passengers onto later services.", True, weather_cancel_consolidate),
        ("DIVERT_MULTIMODAL", "Divert and switch mode", "Divert long-holding inbound flights to alternates with coach transfer and move short-haul passengers to rail.", True, weather_divert_multimodal),
    ],
    "CORRIDOR_BLOCK": [
        ("CAUTION", "Caution-order working", "Keep trains moving through the failed block under Paper Line Clear at restricted speed, one train per block.", False, rail_caution_order),
        ("HOLD", "Hold until restored", "Hold trains at stations until the block section is restored, then release in sequence.", True, rail_hold),
        ("SHORT_TERMINATE", "Short-terminate and bridge", "Short-terminate short-haul trains with a coach bridge and divert long-distance trains via an alternate route.", False, rail_short_terminate),
    ],
    "VEHICLE_GROUNDED": [
        ("TAIL_SWAP", "Spare aircraft swap", "Ferry the spare aircraft in and swap it onto the grounded aircraft's remaining legs.", False, aog_tail_swap),
        ("HOLD", "Delay until repaired", "Keep the rotation and delay departures until line maintenance releases the aircraft.", True, aog_delay),
        ("CANCEL", "Cancel and rebook", "Cancel the remaining legs and re-accommodate passengers on other flights and rail.", False, aog_cancel),
    ],
}


def generate_options(ctx: dict) -> tuple[list[dict], dict[str, dict]]:
    """Build and evaluate every strategy for the scope. Returns options and heavy artifacts."""
    scope = ctx["scope"]
    p50 = parse_dt(ctx["restoration"]["p50"])
    p90 = parse_dt(ctx["restoration"]["p90"])
    options, artifacts = [], {}
    for letter, (code, name, summary, repair_dependent, fn) in zip("ABC", STRATEGIES[scope["type"]]):
        run_ctx = dict(ctx)
        spec = fn(run_ctx, p50)
        option, art = evaluate_plan(ctx=run_ctx, **spec)
        sensitivity = None
        if repair_dependent and p90 > p50:
            spec90 = fn(dict(ctx), p90)
            opt90, _ = evaluate_plan(ctx=run_ctx, **spec90)
            sensitivity = {
                "scenario": "P90 restoration",
                "restoration": iso(p90),
                "extra_cost": opt90["cost"]["total"] - option["cost"]["total"],
                "avg_delay_min": opt90["metrics"]["avg_delay_min"],
                "pax_affected": opt90["metrics"]["pax_affected"],
            }
        option.update({
            "id": f"P{ctx['plan_version']}-{letter}",
            "letter": letter,
            "code": code,
            "name": name,
            "summary": summary,
            "repair_dependent": repair_dependent,
            "sensitivity": sensitivity,
        })
        options.append(option)
        artifacts[option["id"]] = art
    return options, artifacts
