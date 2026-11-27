"""In-memory operational data store.

All mutable state lives here behind a re-entrant lock so that LangGraph worker threads and
API handlers can share it safely. Swapping this for a database-backed repository only
requires re-implementing the public methods.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from app.core.utils import add_min, iso, now
from app.data import reference as ref
from app.data import seed

TIER_RANK = {"PLATINUM": 3, "GOLD": 2, "SILVER": 1, None: 0}
PRIORITY_SSR = {"WCHR", "UMNR", "MEDA"}


def is_priority(p: dict) -> bool:
    return p.get("ssr") in PRIORITY_SSR or p.get("tier") in ("PLATINUM", "GOLD")


def priority_score(p: dict) -> int:
    score = TIER_RANK.get(p.get("tier"), 0)
    if p.get("ssr") in PRIORITY_SSR:
        score += 10
    elif p.get("ssr") == "SRCT":
        score += 2
    return score


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            data = seed.generate(now())
            self.base: datetime = data["base"]
            self.trips: dict[str, dict] = data["trips"]
            self.rotations: dict[str, list[str]] = data["rotations"]
            self.vehicles: dict[str, dict] = data["vehicles"]
            self.crew: dict[str, dict] = data["crew"]
            self.pairings: dict[str, dict] = data["pairings"]
            self.reserves: dict[str, dict[str, list[str]]] = data["reserves"]
            self.passengers: dict[str, dict] = data["passengers"]
            self.pax_by_trip: dict[str, set[str]] = data["pax_by_trip"]
            self.assets: dict[str, dict] = data["assets"]
            self.teams: dict[str, dict] = data["teams"]
            self.pnr_index = {p["pnr"]: pid for pid, p in self.passengers.items()}
            self.incidents: dict[str, dict] = {}
            self.work_orders: dict[str, dict] = {}
            self.notifications: list[dict] = []
            self.plan_artifacts: dict[str, dict] = {}
            self.feed: deque[dict] = deque(maxlen=150)
            self.weather: dict[str, dict] = {}
            self._counters: dict[str, int] = {}

    def next_id(self, prefix: str, start: int = 1001) -> str:
        with self.lock:
            n = self._counters.get(prefix, start)
            self._counters[prefix] = n + 1
            return f"{prefix}-{n}"

    # ---- Trips -----------------------------------------------------------
    def est_dep(self, t: dict) -> datetime:
        return add_min(t["sched_dep"], t["delay_min"])

    def est_arr(self, t: dict) -> datetime:
        return add_min(t["sched_arr"], t["delay_min"])

    def trip_status(self, t: dict, ref_time: datetime | None = None) -> str:
        ref_time = ref_time or now()
        if t["cancelled"]:
            return "CANCELLED"
        if t["diverted_to"]:
            return "DIVERTED"
        if ref_time >= self.est_arr(t):
            return "ARRIVED"
        if ref_time >= self.est_dep(t):
            return "EN_ROUTE"
        if t["delay_min"] >= 15:
            return "DELAYED"
        if (self.est_dep(t) - ref_time).total_seconds() <= 45 * 60:
            return "BOARDING"
        return "ON_TIME"

    def booked(self, trip_id: str) -> int:
        return len(self.pax_by_trip.get(trip_id, ()))

    def spare_seats(self, trip_id: str) -> int:
        t = self.trips[trip_id]
        return max(0, t["capacity"] - self.booked(trip_id))

    def trip_view(self, t: dict, ref_time: datetime | None = None) -> dict:
        return {
            "id": t["id"],
            "number": t["number"],
            "name": t["name"],
            "mode": t["mode"],
            "operator": t["operator"],
            "origin": ref.display_code(t["origin"]),
            "destination": ref.display_code(t["destination"]),
            "origin_city": ref.city_of(t["origin"]),
            "destination_city": ref.city_of(t["destination"]),
            "route": [ref.display_code(s) for s in t["route"]],
            "sched_dep": iso(t["sched_dep"]),
            "sched_arr": iso(t["sched_arr"]),
            "est_dep": iso(self.est_dep(t)),
            "est_arr": iso(self.est_arr(t)),
            "delay_min": t["delay_min"],
            "status": self.trip_status(t, ref_time),
            "vehicle_id": t["vehicle_id"],
            "vehicle_type": t["vehicle_type"],
            "capacity": t["capacity"],
            "booked": self.booked(t["id"]),
            "load_factor": round(self.booked(t["id"]) / t["capacity"], 3),
            "gate": t["gate"],
            "diverted_to": ref.display_code(t["diverted_to"]) if t["diverted_to"] else None,
            "disruption_ids": list(t["disruption_ids"]),
            "remarks": t["remarks"],
        }

    # ---- Passengers ------------------------------------------------------
    def pax_view(self, p: dict, include_legs: bool = True) -> dict:
        view = {
            "id": p["id"],
            "pnr": p["pnr"],
            "name": f"{p['first_name']} {p['last_name']}",
            "first_name": p["first_name"],
            "last_name": p["last_name"],
            "tier": p["tier"],
            "ssr": p["ssr"],
            "language": p["language"],
            "language_label": ref.LANGUAGES.get(p["language"], p["language"]),
            "channel": p["channel"],
            "cabin": p["cabin"],
            "status": p["status"],
            "priority": is_priority(p),
        }
        if include_legs:
            view["legs"] = [self.trip_view(self.trips[t]) for t in p["legs"]]
        return view

    def crew_view(self, cid: str) -> dict:
        c = self.crew[cid]
        return {**c, "role_label": ref.ROLE_LABELS.get(c["role"], c["role"]), "base": ref.display_code(c["base"])}

    # ---- Assets ----------------------------------------------------------
    def asset_view(self, a: dict) -> dict:
        return {
            "id": a["id"],
            "name": a["name"],
            "type": a["type"],
            "category": a["category"],
            "location": ref.display_code(a["location"]),
            "corridor": [ref.display_code(c) for c in a["corridor"]] if a.get("corridor") else None,
            "criticality": a["criticality"],
            "health": a["health"],
            "status": a["status"],
            "metrics": a["metrics"],
            "baseline": a["baseline"],
            "last_inspection": iso(a["last_inspection"]),
        }

    def add_feed(self, item: dict) -> dict:
        with self.lock:
            self.feed.appendleft(item)
        return item


store = Store()
