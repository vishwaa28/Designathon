"""Deterministic generator for the mock operating day.

Produces ~70 flights built from real aircraft rotations, crew pairings with duty limits,
~20k passenger bookings (including air-air connections) and an asset registry with live
telemetry baselines.
"""
from __future__ import annotations

import copy
import random
import string
from datetime import datetime, timedelta

from app.core.utils import add_min, haversine_km, round_to
from app.data import reference as ref

FLIGHT_TURN_MIN = 45
ATR_TURN_MIN = 30



def _flight_minutes(a: str, b: str) -> int:
    pa, pb = ref.place(a), ref.place(b)
    km = haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"])
    return round_to(35 + km / 780 * 60)


def _segment_km(a: str, b: str) -> float:
    pa, pb = ref.place(a), ref.place(b)
    return haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"]) * 1.25


class _Ids:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.pnrs: set[str] = set()
        self.counters: dict[str, int] = {}

    def seq(self, prefix: str, start: int = 1) -> str:
        n = self.counters.get(prefix, start)
        self.counters[prefix] = n + 1
        return f"{prefix}{n}"

    def pnr(self) -> str:
        alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"
        while True:
            code = "".join(self.rng.choice(alphabet) for _ in range(6))
            if code not in self.pnrs:
                self.pnrs.add(code)
                return code


def generate(now: datetime) -> dict:
    rng = random.Random(42)
    ids = _Ids(rng)
    base = now.replace(minute=0, second=0, microsecond=0)

    trips: dict[str, dict] = {}
    rotations: dict[str, list[str]] = {}
    vehicles: dict[str, dict] = {}
    crew: dict[str, dict] = {}
    pairings: dict[str, dict] = {}

    def new_crew_member(role: str, crew_base: str, limit_h: float) -> str:
        cid = ids.seq("C-", 1001)
        crew[cid] = {
            "id": cid,
            "name": f"{rng.choice(ref.FIRST_NAMES)} {rng.choice(ref.LAST_NAMES)}",
            "role": role,
            "base": crew_base,
            "duty_limit_h": limit_h,
            "status": "ON_DUTY",
            "pairing_id": None,
        }
        return cid

    # ---- Flights ---------------------------------------------------------
    flight_no = 101
    for i, (tail, ac_type, seats, hub, dests) in enumerate(ref.AIRCRAFT):
        turn = ATR_TURN_MIN if ac_type.startswith("ATR") else FLIGHT_TURN_MIN
        t = add_min(base, -180 + i * 40 + rng.randint(-10, 10))
        legs: list[tuple[str, str]] = []
        for d in dests:
            legs += [(hub, d), (d, hub)]
        rotations[tail] = []
        vehicles[tail] = {"id": tail, "type": ac_type, "seats": seats, "base": hub}
        for seq, (o, d) in enumerate(legs):
            dur = _flight_minutes(o, d)
            tid = f"MR{flight_no}"
            trips[tid] = {
                "id": tid,
                "number": f"MR {flight_no}",
                "name": f"{ref.city_of(o)} to {ref.city_of(d)}",
                "operator": ref.AIRLINE["name"],
                "origin": o,
                "destination": d,
                "route": [o, d],
                "sched_dep": t,
                "sched_arr": add_min(t, dur),
                "delay_min": 0,
                "cancelled": False,
                "diverted_to": None,
                "vehicle_id": tail,
                "vehicle_type": ac_type,
                "capacity": seats,
                "rotation_seq": seq,
                "pairing_id": None,
                "gate": f"{rng.choice(['T1', 'T2', 'T3'])}-{rng.randint(1, 58)}",
                "disruption_ids": [],
                "remarks": "",
            }
            rotations[tail].append(tid)
            flight_no += 1
            t = add_min(t, dur + turn)

        # Crew pairings: change crew at hub before an out-leg if the pair would breach the buffer.
        legs_ids = rotations[tail]
        pairs = [legs_ids[k:k + 2] for k in range(0, len(legs_ids), 2)]
        current: dict | None = None
        cabin_count = 2 if ac_type.startswith("ATR") else 4
        for pair in pairs:
            first, last = trips[pair[0]], trips[pair[-1]]
            if current:
                landings = len(current["trip_ids"]) + len(pair)
                limit = 13.0 - 0.5 * max(0, landings - 2)
                projected = (add_min(last["sched_arr"], 30) - current["duty_start"]).total_seconds() / 3600
                if projected > limit - 0.75:
                    current = None
            if current is None:
                pid = ids.seq("PR-", 501)
                current = {"id": pid, "base": hub, "crew_ids": [], "trip_ids": [],
                           "duty_start": add_min(first["sched_dep"], -60)}
                roles = ["CPT", "FO"] + ["CC"] * cabin_count
                for role in roles:
                    cid = new_crew_member(role, hub, 0.0)
                    crew[cid]["pairing_id"] = pid
                    current["crew_ids"].append(cid)
                pairings[pid] = current
            current["trip_ids"] += pair
            for tid in pair:
                trips[tid]["pairing_id"] = current["id"]
        for pid in {trips[t]["pairing_id"] for t in legs_ids}:
            p = pairings[pid]
            landings = len(p["trip_ids"])
            cockpit_limit = 13.0 - 0.5 * max(0, landings - 2)
            for cid in p["crew_ids"]:
                crew[cid]["duty_limit_h"] = cockpit_limit if crew[cid]["role"] in ("CPT", "FO") else cockpit_limit + 1.0

    for tail, ac_type, seats, hub in ref.SPARE_AIRCRAFT:
        vehicles[tail] = {"id": tail, "type": ac_type, "seats": seats, "base": hub, "spare": True}
        rotations[tail] = []

    # Reserve crew
    reserves: dict[str, dict[str, list[str]]] = {}
    for crew_base, roles in ref.RESERVE_CREW.items():
        reserves[crew_base] = {}
        for role, count in roles.items():
            reserves[crew_base][role] = []
            for _ in range(count):
                limit = 13.0
                cid = new_crew_member(role, crew_base, limit)
                crew[cid]["status"] = "RESERVE"
                reserves[crew_base][role].append(cid)

    # ---- Passengers ------------------------------------------------------
    passengers: dict[str, dict] = {}
    pax_by_trip: dict[str, set[str]] = {tid: set() for tid in trips}
    targets = {tid: int(t["capacity"] * rng.uniform(0.72, 0.95)) for tid, t in trips.items()}

    def make_pax(legs: list[str]) -> None:
        first = trips[legs[0]]
        r = rng.random()
        tier = "PLATINUM" if r < 0.03 else "GOLD" if r < 0.10 else "SILVER" if r < 0.22 else None
        s = rng.random()
        if s < 0.02:
            ssr = "WCHR"
        elif s < 0.027:
            ssr = "UMNR"
        elif s < 0.032:
            ssr = "MEDA"
        elif s < 0.05:
            ssr = "SRCT"
        else:
            ssr = None
        lang = "en" if rng.random() < 0.5 else ref.CITY_LANGUAGE.get(ref.city_of(first["origin"]), "hi")
        c = rng.random()
        channel = "APP" if c < 0.35 else "SMS" if c < 0.65 else "WHATSAPP" if c < 0.9 else "EMAIL"
        premium = rng.random() < 0.08
        cabin = "Business" if premium else "Economy"
        fare = 0
        for tid in legs:
            t = trips[tid]
            km = sum(_segment_km(a, b) for a, b in zip(t["route"], t["route"][1:]))
            leg_fare = 3200 + km * 3.6
            fare += leg_fare * (2.8 if premium else 1.0) * rng.uniform(0.85, 1.2)
        pid = ids.seq("P", 100001)
        fn, ln = rng.choice(ref.FIRST_NAMES), rng.choice(ref.LAST_NAMES)
        passengers[pid] = {
            "id": pid,
            "pnr": ids.pnr(),
            "first_name": fn,
            "last_name": ln,
            "legs": list(legs),
            "original_legs": list(legs),
            "tier": tier,
            "ssr": ssr,
            "language": lang,
            "channel": channel,
            "cabin": cabin,
            "fare": int(round(fare, -1)),
            "phone": f"+91 9{rng.randint(10, 99)}xx xx{rng.randint(100, 999)}",
            "email": f"{fn.lower()}.{ln.lower().replace(chr(39), '')}{rng.randint(1, 99)}@mail.example",
            "status": "CONFIRMED",
        }
        for tid in legs:
            pax_by_trip[tid].add(pid)

    def has_room(tid: str, n: int) -> bool:
        return len(pax_by_trip[tid]) + n <= targets[tid]

    trip_list = sorted(trips.values(), key=lambda t: t["sched_dep"])
    for inbound in trip_list:
        arr_at, arr_t = inbound["destination"], inbound["sched_arr"]
        rules = []
        if arr_at == ref.HUB_AIRPORT:
            rules.append((arr_at, 60, 300, (5, 14), 2))
        if arr_at == "BLR":
            rules.append((arr_at, 60, 300, (3, 8), 1))
        for from_node, lo, hi, (nmin, nmax), picks in rules:
            cands = [
                t for t in trip_list
                if t["origin"] == from_node
                and add_min(arr_t, lo) <= t["sched_dep"] <= add_min(arr_t, hi)
                and ref.city_of(t["destination"]) != ref.city_of(inbound["origin"])
            ]
            rng.shuffle(cands)
            for onward in cands[:picks]:
                n = rng.randint(nmin, nmax)
                if has_room(inbound["id"], n) and has_room(onward["id"], n):
                    for _ in range(n):
                        make_pax([inbound["id"], onward["id"]])

    for tid in trips:
        while len(pax_by_trip[tid]) < targets[tid]:
            make_pax([tid])

    hub_departures = [t for t in trip_list if t["origin"] == ref.HUB_AIRPORT and t["sched_dep"] >= add_min(base, 90)]
    for i, c in enumerate(ref.CONTACT_PASSENGERS):
        trip = hub_departures[i % len(hub_departures)] if hub_departures else trip_list[-1]
        pid = ids.seq("P", 100001)
        ids.pnrs.add(c["pnr"])
        passengers[pid] = {
            "id": pid, "pnr": c["pnr"], "first_name": c["first_name"], "last_name": c["last_name"],
            "legs": [trip["id"]], "original_legs": [trip["id"]], "tier": c["tier"], "ssr": None,
            "language": c["language"], "channel": "EMAIL", "cabin": "Economy", "fare": 6480,
            "phone": c["phone"], "email": c["email"], "status": "CONFIRMED", "contact": True,
        }
        pax_by_trip[trip["id"]].add(pid)

    # ---- Assets ----------------------------------------------------------
    assets: dict[str, dict] = {}
    for a in ref.INFRA_ASSETS:
        item = copy.deepcopy(a)
        item.update({
            "health": rng.randint(88, 99),
            "status": "OPERATIONAL",
            "baseline": dict(item["metrics"]),
            "last_inspection": base - timedelta(days=rng.randint(2, 40)),
        })
        assets[item["id"]] = item
    for vid, v in vehicles.items():
        metrics = {"hyd_sys_b_psi": 3000.0, "egt_margin_c": float(rng.randint(32, 58)), "apu_hours_since_check": float(rng.randint(40, 380))}
        category, typ = "Fleet", "AIRCRAFT"
        assets[vid] = {
            "id": vid, "name": f"{v['type']} {vid}", "type": typ, "category": category,
            "location": v["base"], "criticality": "HIGH", "metrics": metrics, "baseline": dict(metrics),
            "health": rng.randint(85, 99), "status": "OPERATIONAL",
            "last_inspection": base - timedelta(days=rng.randint(1, 20)), "spare": v.get("spare", False),
        }

    teams = {t["id"]: {**t, "status": "AVAILABLE"} for t in ref.MAINTENANCE_TEAMS}

    return {
        "base": base,
        "trips": trips,
        "rotations": rotations,
        "vehicles": vehicles,
        "crew": crew,
        "pairings": pairings,
        "reserves": reserves,
        "passengers": passengers,
        "pax_by_trip": pax_by_trip,
        "assets": assets,
        "teams": teams,
    }
